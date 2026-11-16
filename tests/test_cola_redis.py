"""Cola real: Redis en contenedor desechable, la API encola con arq y un worker en modo burst
procesa. Los dobles solo reemplazan a los proveedores de embeddings y visión."""

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest
from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import Worker
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.providers.cola import ColaArq, obtener_cola
from app.services import catalogo
from app.worker import WorkerSettings, al_arrancar, ingestar_archivo
from main import app
from tests.dobles import proveedor_doble
from tests.pdf_minimo import pdf_minimo

URL_LOTES = "/api/espacios/laboral/colecciones/agricultura/lotes"


async def _vaciar_redis(redis_url: str) -> None:
    pool = await create_pool(RedisSettings.from_dsn(redis_url))
    await pool.flushdb()
    await pool.aclose()


def test_lote_encolado_en_redis_lo_procesa_el_worker(
    client: TestClient,
    db: Session,
    redis_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "INGESTA_TEMPORAL", tmp_path)
    catalogo.crear_espacio(db, "laboral", "Laboral")
    catalogo.crear_coleccion(db, "laboral", "agricultura", "Agricultura")
    app.dependency_overrides[obtener_cola] = lambda: ColaArq(redis_url)
    archivos = [
        ("archivos", ("olivo.pdf", pdf_minimo(["Riego del olivo"]))),
        ("archivos", ("poda.pdf", pdf_minimo(["Poda del olivo"]))),
    ]
    asyncio.run(_vaciar_redis(redis_url))  # Redis es compartido por la sesión de tests
    trabajo_id = client.post(URL_LOTES, files=archivos).json()["id"]

    @contextmanager
    def sesion() -> Generator[Session, None, None]:
        yield db

    async def correr_worker() -> int:
        # arq toma el event loop al construir el Worker: tiene que nacer dentro de este.
        worker = Worker(
            functions=[ingestar_archivo],
            redis_settings=RedisSettings.from_dsn(redis_url),
            on_startup=al_arrancar,
            ctx={
                "abrir_sesion": sesion,
                "obtener_proveedor": proveedor_doble,
                "obtener_vision": lambda: None,
            },
            burst=True,
            max_jobs=WorkerSettings.max_jobs,
            max_tries=WorkerSettings.max_tries,
            handle_signals=False,
        )
        try:
            return await worker.run_check()  # en arq 0.28 es una corrutina
        finally:
            await worker.close()

    completados = asyncio.run(correr_worker())

    cuerpo = client.get(f"/api/trabajos/{trabajo_id}").json()
    assert completados == len(archivos)
    assert (cuerpo["estado"], cuerpo["ingeridos"], cuerpo["errores"]) == ("terminado", 2, 0)
