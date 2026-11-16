from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "biblioteca-rag"}


def test_base_es_postgres_con_pgvector(db: Session) -> None:
    db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    distancia = db.execute(text("SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector")).scalar_one()

    assert db.get_bind().dialect.name == "postgresql"
    assert distancia == 1.0


def test_sin_origenes_configurados_no_se_permite_ningun_origen_cruzado(client: TestClient) -> None:
    from app.config.settings import settings

    assert settings.CORS_ORIGINS == []

    simple = client.get("/health", headers={"Origin": "https://cualquiera.example"})
    previa = client.options(
        "/api/espacios",
        headers={"Origin": "https://cualquiera.example", "Access-Control-Request-Method": "POST"},
    )

    assert "access-control-allow-origin" not in simple.headers
    assert "access-control-allow-origin" not in previa.headers
