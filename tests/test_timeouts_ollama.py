"""C10: un Ollama colgado no puede retener una página ni una respuesta la hora del trabajo."""

import socket
import threading
import time
from collections.abc import Generator

import pytest

from app.config.constantes import ProveedorLLM, ProveedorVision
from app.config.settings import Settings
from app.providers.llm import ErrorLLM, crear_llm, redactar
from app.providers.vision import crear_vision, describir_imagen

TIMEOUT_DE_PRUEBA = 0.5
MARGEN = 5.0  # muy por debajo de cualquier espera «infinita»


@pytest.fixture
def ollama_colgado() -> Generator[str, None, None]:
    """Acepta conexiones y nunca responde."""
    servidor = socket.socket()
    servidor.bind(("127.0.0.1", 0))
    servidor.listen()
    abiertas: list[socket.socket] = []
    corriendo = True

    def aceptar() -> None:
        servidor.settimeout(0.2)
        while corriendo:
            try:
                conexion, _ = servidor.accept()
                abiertas.append(conexion)
            except TimeoutError:
                continue

    hilo = threading.Thread(target=aceptar, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{servidor.getsockname()[1]}"
    corriendo = False
    hilo.join()
    for conexion in abiertas:
        conexion.close()
    servidor.close()


def _config(url: str) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]  # el .env local no decide el test
        DATABASE_URL="x",
        SECRET_KEY="x",
        OLLAMA_BASE_URL=url,
        VISION_PROVIDER=ProveedorVision.OLLAMA,
        LLM_PROVIDER=ProveedorLLM.OLLAMA,
    )


def test_la_vision_abandona_a_un_ollama_colgado(
    ollama_colgado: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.providers.vision.TIMEOUT_VISION_SEGUNDOS", TIMEOUT_DE_PRUEBA)
    vision = crear_vision(_config(ollama_colgado))
    assert vision is not None
    inicio = time.monotonic()

    with pytest.raises(ErrorLLM):
        describir_imagen(vision, b"\x89PNG")

    assert time.monotonic() - inicio < MARGEN


def test_el_llm_local_abandona_a_un_ollama_colgado(
    ollama_colgado: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from langchain_core.messages import HumanMessage

    monkeypatch.setattr("app.providers.llm.TIMEOUT_LLM_SEGUNDOS", TIMEOUT_DE_PRUEBA)
    llm = crear_llm(_config(ollama_colgado))
    inicio = time.monotonic()

    with pytest.raises(ErrorLLM):
        redactar(llm, [HumanMessage("hola")])

    assert time.monotonic() - inicio < MARGEN


def test_los_embeddings_locales_abandonan_a_un_ollama_colgado(
    ollama_colgado: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config.constantes import ProveedorEmbeddings
    from app.providers.embeddings import (
        ErrorEmbeddings,
        crear_proveedor_embeddings,
        embeber_pregunta,
    )

    monkeypatch.setattr("app.providers.embeddings.TIMEOUT_EMBEDDINGS_SEGUNDOS", TIMEOUT_DE_PRUEBA)
    config = _config(ollama_colgado).model_copy(
        update={"EMBEDDINGS_PROVIDER": ProveedorEmbeddings.OLLAMA}
    )
    inicio = time.monotonic()

    with pytest.raises(ErrorEmbeddings):
        embeber_pregunta(crear_proveedor_embeddings(config), "hola")

    assert time.monotonic() - inicio < MARGEN
