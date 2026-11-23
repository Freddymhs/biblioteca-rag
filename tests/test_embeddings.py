import json

import httpx
import pytest
from langchain_ollama import OllamaEmbeddings
from pydantic import SecretStr

from app.common.errors import AppError
from app.config.constantes import DIMENSION_EMBEDDING, LOTE_EMBEDDINGS, ProveedorEmbeddings
from app.config.settings import Settings
from app.providers.embeddings import (
    CloudflareEmbeddings,
    ErrorEmbeddings,
    crear_proveedor_embeddings,
)

ACCOUNT_ID = "cuenta-de-prueba"
TOKEN = "token-de-prueba"
URL_ESPERADA = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/v1/embeddings"


def _config(**valores: object) -> Settings:
    """Sin leer el .env local: la configuración de esta máquina no decide el resultado."""
    return Settings(_env_file=None, DATABASE_URL="x", SECRET_KEY="x", **valores)  # type: ignore[call-arg, arg-type]  # _env_file es de pydantic-settings


def _cuerpo_openai(vectores: list[list[float]]) -> dict:
    """Cuerpo literal de la API de Embeddings de OpenAI, que Workers AI dice implementar."""
    return {
        "object": "list",
        "data": [
            {"object": "embedding", "index": indice, "embedding": vector}
            for indice, vector in reversed(list(enumerate(vectores)))  # fuera de orden a propósito
        ],
        "model": "@cf/baai/bge-m3",
        "usage": {"prompt_tokens": 8, "total_tokens": 8},
    }


def _vector(valor: float) -> list[float]:
    return [valor] * DIMENSION_EMBEDDING


def _cliente(responder) -> tuple[CloudflareEmbeddings, list[httpx.Request]]:
    pedidos: list[httpx.Request] = []

    def transporte(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return responder(pedido)

    cliente = CloudflareEmbeddings(
        account_id=ACCOUNT_ID,
        api_token=SecretStr(TOKEN),
        modelo="@cf/baai/bge-m3",
        cliente_http=httpx.Client(transport=httpx.MockTransport(transporte)),
    )
    return cliente, pedidos


def _eco(pedido: httpx.Request) -> httpx.Response:
    textos = json.loads(pedido.content)["input"]
    return httpx.Response(200, json=_cuerpo_openai([_vector(i / 10) for i in range(len(textos))]))


def test_pedido_al_endpoint_openai_de_cloudflare() -> None:
    cliente, pedidos = _cliente(_eco)

    cliente.embed_query("¿Cuál es el Kc del olivo?")

    pedido = pedidos[0]
    assert str(pedido.url) == URL_ESPERADA
    assert pedido.headers["Authorization"] == f"Bearer {TOKEN}"
    assert json.loads(pedido.content) == {
        "model": "@cf/baai/bge-m3",
        "input": ["¿Cuál es el Kc del olivo?"],
    }


def test_respeta_el_orden_por_index_y_trocea_en_lotes() -> None:
    cliente, pedidos = _cliente(_eco)
    textos = [f"texto {i}" for i in range(LOTE_EMBEDDINGS + 3)]

    vectores = cliente.embed_documents(textos)

    assert len(pedidos) == 2
    assert len(vectores) == len(textos)
    assert vectores[1][0] == pytest.approx(0.1)
    assert vectores[LOTE_EMBEDDINGS + 2][0] == pytest.approx(0.2)


@pytest.mark.parametrize(
    ("respuesta", "mensaje"),
    [
        (httpx.Response(401, json={"success": False, "errors": [{"code": 10000}]}), "401"),
        (httpx.Response(200, json=_cuerpo_openai([[0.1, 0.2]])), "Dimensión"),
        (httpx.Response(200, json={"data": []}), "llegaron 0"),
    ],
    ids=["no-autorizado", "dimension-equivocada", "sin-vectores"],
)
def test_respuestas_invalidas_lanzan_error(respuesta: httpx.Response, mensaje: str) -> None:
    cliente, _ = _cliente(lambda _pedido: respuesta)

    with pytest.raises(ErrorEmbeddings, match=mensaje):
        cliente.embed_query("hola")


@pytest.mark.parametrize(
    "respuesta",
    [
        httpx.Response(200, text="<html>Bad gateway</html>"),
        httpx.Response(200, json={"data": [{"embedding": [0.1] * DIMENSION_EMBEDDING}]}),
        httpx.Response(200, json={"data": [{"index": 0}]}),
        httpx.Response(200, json={"data": "no-es-lista"}),
        httpx.Response(200, json=["no", "es", "objeto"]),
    ],
    ids=["no-json", "sin-index", "sin-embedding", "data-no-lista", "cuerpo-no-objeto"],
)
def test_cuerpo_mal_formado_es_error_del_proveedor(respuesta: httpx.Response) -> None:
    cliente, _ = _cliente(lambda _pedido: respuesta)

    with pytest.raises(ErrorEmbeddings, match="formato"):
        cliente.embed_query("hola")


def test_cloudflare_sin_credenciales_responde_503() -> None:
    config = _config(CLOUDFLARE_ACCOUNT_ID="")

    with pytest.raises(AppError) as error:
        crear_proveedor_embeddings(config)

    assert error.value.status_code == 503


def test_ollama_se_elige_por_configuracion() -> None:
    config = _config(
        EMBEDDINGS_PROVIDER=ProveedorEmbeddings.OLLAMA,
    )

    proveedor = crear_proveedor_embeddings(config)

    assert isinstance(proveedor.cliente, OllamaEmbeddings)
    assert proveedor.modelo_id == "bge-m3"
    assert proveedor.quien_responde == "ollama:bge-m3"  # trazas: qué proveedor respondió


def test_cloudflare_con_credenciales_identifica_el_modelo() -> None:
    config = _config(
        CLOUDFLARE_ACCOUNT_ID=ACCOUNT_ID,
        CLOUDFLARE_API_TOKEN=SecretStr(TOKEN),
    )

    proveedor = crear_proveedor_embeddings(config)

    assert isinstance(proveedor.cliente, CloudflareEmbeddings)
    assert proveedor.modelo_id == "bge-m3"
    assert proveedor.quien_responde == "cloudflare:@cf/baai/bge-m3"


def test_b2_un_modelo_sin_equivalencia_medida_lleva_el_proveedor() -> None:
    """Solo comparten identificador los modelos medidos (6.8); otro modelo no se mezcla."""
    config = _config(
        EMBEDDINGS_PROVIDER=ProveedorEmbeddings.OLLAMA, OLLAMA_EMBEDDINGS_MODEL="nomic"
    )

    proveedor = crear_proveedor_embeddings(config)

    assert proveedor.modelo_id == "ollama:nomic"
