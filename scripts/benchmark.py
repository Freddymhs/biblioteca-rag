"""Benchmark de embeddings (tarea 1.9).

    uv run python scripts/benchmark.py             # Ollama vs Cloudflare + latencias
    uv run python scripts/benchmark.py --solo-ollama

Criterios: coseno del mismo texto Ollama vs Cloudflare > 0,99 (si no, cambiar de proveedor obliga
a re-embeber) y embedding de una pregunta < 1 s. El tercero —los 89 documentos en una noche— se
mide corriendo `app.cli.ingestar` sobre el corpus completo y leyendo su resumen.
"""

import argparse
import math
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Imports tardíos intencionales: necesitan la raíz del repo en sys.path, agregada justo arriba.
from app.config.constantes import ProveedorEmbeddings  # noqa: E402
from app.config.settings import settings  # noqa: E402
from app.providers.embeddings import (  # noqa: E402
    ProveedorDeEmbeddings,
    crear_proveedor_embeddings,
)

COSENO_MINIMO = 0.99
LATENCIA_MAXIMA_SEGUNDOS = 1.0
REPETICIONES_LATENCIA = 10
TEXTOS = [
    "¿Cuál es el coeficiente de cultivo Kc del olivo en plena producción?",
    "La demanda hídrica diaria del nogal en Choapa interior es de 6,2 mm en diciembre.",
    "Plantas duras: aquellas que soportan fuertes heladas, como coles, espinacas y cebolla.",
    "Dragon fruit contains antioxidants such as flavonoids and betalains.",
    "Manejo integrado del cultivo de maracuyá: riego, poda, plagas y cosecha.",
]


def coseno(a: list[float], b: list[float]) -> float:
    producto = sum(x * y for x, y in zip(a, b, strict=True))
    return producto / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def latencia_pregunta(proveedor: ProveedorDeEmbeddings) -> float:
    proveedor.cliente.embed_query(TEXTOS[0])  # calentamiento: carga del modelo
    tiempos = []
    for _ in range(REPETICIONES_LATENCIA):
        inicio = time.perf_counter()
        proveedor.cliente.embed_query(TEXTOS[0])
        tiempos.append(time.perf_counter() - inicio)
    return statistics.median(tiempos)


def main() -> int:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--solo-ollama", action="store_true")
    solo_ollama = argumentos.parse_args().solo_ollama

    ollama = crear_proveedor_embeddings(
        settings.model_copy(update={"EMBEDDINGS_PROVIDER": ProveedorEmbeddings.OLLAMA})
    )
    proveedores = [ollama]
    if not solo_ollama:
        cloudflare = crear_proveedor_embeddings(
            settings.model_copy(update={"EMBEDDINGS_PROVIDER": ProveedorEmbeddings.CLOUDFLARE})
        )
        proveedores.append(cloudflare)

    fallos = 0
    for proveedor in proveedores:
        mediana = latencia_pregunta(proveedor)
        ok = mediana < LATENCIA_MAXIMA_SEGUNDOS
        fallos += not ok
        print(
            f"{'OK ' if ok else 'MAL'} latencia {proveedor.modelo_id}: {mediana:.3f} s "
            f"(mediana de {REPETICIONES_LATENCIA}, máximo {LATENCIA_MAXIMA_SEGUNDOS} s)"
        )

    if not solo_ollama:
        vectores_ollama = ollama.cliente.embed_documents(TEXTOS)
        vectores_cloudflare = proveedores[1].cliente.embed_documents(TEXTOS)
        cosenos = [coseno(a, b) for a, b in zip(vectores_ollama, vectores_cloudflare, strict=True)]
        minimo = min(cosenos)
        ok = minimo > COSENO_MINIMO
        fallos += not ok
        print(
            f"{'OK ' if ok else 'MAL'} coseno Ollama vs Cloudflare: mínimo {minimo:.4f} "
            f"sobre {len(TEXTOS)} textos (umbral {COSENO_MINIMO})"
        )

    print(f"Chequeos: {len(proveedores) + (not solo_ollama)} · fallidos: {fallos}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
