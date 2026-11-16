"""Paquete de dominio `facturas` (tarea 3.3): el ejemplo de referencia del concepto.

Las herramientas son SQL FIJO sobre los datos confirmados (`extraccion.confirmados`, JSONB). Los
filtros que propone el LLM llegan como parámetros enlazados; un filtro ausente (NULL) no filtra.
"""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text

from app.dominio.base import FilaCalculo, HerramientaSQL, PaqueteDominio

NOMBRE = "facturas"
# Plausibilidad: medido el 2026-11-16, llama3.2:3b leyó «12-03-2026» como el año 1203 y la fecha
# pasaba como válida. Fuera de este rango la extracción queda con error, para que la corrija
# una persona en el formulario.
ANIO_MINIMO = 1990
ANIO_MAXIMO = 2100
MAX_LARGO_TEXTO = 200
LIMITE_POR_EMISOR = 5
MAX_LIMITE_POR_EMISOR = 20
PATRON_MONEDA = r"^[A-Z]{3}$"
# Montos acotados: un `1E+200000` validaba y hacía fallar todo cálculo de la colección.
MAX_DIGITOS_MONTO = 15
DECIMALES_MONTO = 2
MAX_DIGITOS_CANTIDAD = 12
DECIMALES_CANTIDAD = 3


class LineaFactura(BaseModel):
    descripcion: str = Field(max_length=MAX_LARGO_TEXTO)
    cantidad: Decimal = Field(
        gt=0, max_digits=MAX_DIGITOS_CANTIDAD, decimal_places=DECIMALES_CANTIDAD
    )
    precio_unitario: Decimal = Field(
        ge=0, max_digits=MAX_DIGITOS_MONTO, decimal_places=DECIMALES_MONTO
    )


class Factura(BaseModel):
    """Datos de una factura. Su JSON Schema es el formulario de confirmación."""

    numero: str = Field(min_length=1, max_length=MAX_LARGO_TEXTO, description="folio")
    fecha: date = Field(description="fecha de emisión")
    emisor: str = Field(min_length=1, max_length=MAX_LARGO_TEXTO)
    rut_emisor: str | None = Field(default=None, max_length=MAX_LARGO_TEXTO)
    receptor: str | None = Field(default=None, max_length=MAX_LARGO_TEXTO)
    # Obligatoria: un default «CLP» la suponía sin que nadie la hubiera leído en la factura.
    moneda: str = Field(pattern=PATRON_MONEDA, description="código ISO 4217, ej. CLP o USD")
    neto: Decimal | None = Field(
        default=None, ge=0, max_digits=MAX_DIGITOS_MONTO, decimal_places=DECIMALES_MONTO
    )
    iva: Decimal | None = Field(
        default=None, ge=0, max_digits=MAX_DIGITOS_MONTO, decimal_places=DECIMALES_MONTO
    )
    total: Decimal = Field(ge=0, max_digits=MAX_DIGITOS_MONTO, decimal_places=DECIMALES_MONTO)
    lineas: list[LineaFactura] = Field(default_factory=list)

    @field_validator("fecha")
    @classmethod
    def fecha_plausible(cls, fecha: date) -> date:
        if not ANIO_MINIMO <= fecha.year <= ANIO_MAXIMO:
            raise ValueError(f"año {fecha.year} fuera de {ANIO_MINIMO}–{ANIO_MAXIMO}")
        return fecha


def texto_para_embeber(datos: BaseModel) -> str:
    factura = Factura.model_validate(datos.model_dump())
    lineas = "; ".join(
        f"{linea.cantidad} × {linea.descripcion} a {_monto(linea.precio_unitario, factura.moneda)}"
        for linea in factura.lineas
    )
    partes = [
        f"Factura N° {factura.numero} del {factura.fecha.isoformat()}",
        f"emitida por {factura.emisor}"
        + (f" (RUT {factura.rut_emisor})" if factura.rut_emisor else ""),
        f"a {factura.receptor}" if factura.receptor else "",
        f"total {_monto(factura.total, factura.moneda)}",
        f"detalle: {lineas}" if lineas else "",
    ]
    return ", ".join(parte for parte in partes if parte) + "."


# ── Herramientas SQL fijas ────────────────────────────────────────────────────


class FiltroFacturas(BaseModel):
    desde: date | None = Field(default=None, description="fecha mínima de emisión (incluida)")
    hasta: date | None = Field(default=None, description="fecha máxima de emisión (incluida)")
    emisor: str | None = Field(
        default=None, max_length=MAX_LARGO_TEXTO, description="parte del nombre del emisor"
    )


class FiltroPorEmisor(FiltroFacturas):
    limite: int = Field(default=LIMITE_POR_EMISOR, ge=1, le=MAX_LIMITE_POR_EMISOR)


# Solo datos confirmados de la colección; filtros opcionales sin comodines (strpos, no LIKE).
_FACTURAS = """
WITH facturas AS (
    SELECT d.id AS documento_id,
           e.confirmados->>'numero' AS numero,
           (e.confirmados->>'fecha')::date AS fecha,
           e.confirmados->>'emisor' AS emisor,
           (e.confirmados->>'total')::numeric AS total,
           e.confirmados->>'moneda' AS moneda
    FROM extraccion e
    JOIN documento d ON d.id = e.documento_id
    WHERE d.coleccion_id = :coleccion_id
      AND e.paquete = :paquete
      AND e.estado = CAST(:estado_confirmada AS estado_extraccion)
      AND (CAST(:desde AS date) IS NULL OR (e.confirmados->>'fecha')::date >= :desde)
      AND (CAST(:hasta AS date) IS NULL OR (e.confirmados->>'fecha')::date <= :hasta)
      AND (CAST(:emisor AS text) IS NULL
           OR strpos(lower(e.confirmados->>'emisor'), lower(CAST(:emisor AS text))) > 0)
)
"""

SQL_TOTAL = text(
    _FACTURAS
    + """
SELECT moneda, SUM(total) AS total, COUNT(*) AS cantidad, array_agg(documento_id) AS documento_ids
FROM facturas GROUP BY moneda ORDER BY moneda
"""
)
SQL_POR_EMISOR = text(
    _FACTURAS
    + """
, por_emisor AS (
    SELECT emisor, moneda, SUM(total) AS total, COUNT(*) AS cantidad,
           array_agg(documento_id) AS documento_ids,
           ROW_NUMBER() OVER (PARTITION BY moneda ORDER BY SUM(total) DESC) AS puesto
    FROM facturas GROUP BY emisor, moneda
)
SELECT emisor, moneda, total, cantidad, documento_ids
FROM por_emisor WHERE puesto <= :limite ORDER BY moneda, puesto
"""
)
SQL_MAS_ALTA = text(
    _FACTURAS
    + """
SELECT DISTINCT ON (moneda) numero, fecha, emisor, moneda, total,
       ARRAY[documento_id] AS documento_ids
FROM facturas ORDER BY moneda, total DESC, fecha DESC
"""
)


def _facturas(cantidad: int) -> str:
    return f"{cantidad} factura" if cantidad == 1 else f"{cantidad} facturas"


def _monto(valor: Decimal, moneda: str) -> str:
    entero = f"{valor:,.0f}".replace(",", ".")
    return f"{entero} {moneda}"


def _periodo(filtro: BaseModel) -> str:
    datos = FiltroFacturas.model_validate(filtro.model_dump())
    partes = [
        f"desde el {datos.desde.isoformat()}" if datos.desde else "",
        f"hasta el {datos.hasta.isoformat()}" if datos.hasta else "",
        f"del emisor «{datos.emisor}»" if datos.emisor else "",
    ]
    texto = " ".join(parte for parte in partes if parte)
    return f" ({texto})" if texto else ""


def _formatear_total(filtro: BaseModel, filas: Sequence[FilaCalculo]) -> str:
    if not filas:
        return f"No hay facturas confirmadas{_periodo(filtro)}."
    montos = "; ".join(
        f"{_monto(fila['total'], fila['moneda'])} en {_facturas(fila['cantidad'])}"
        for fila in filas
    )
    return f"Total facturado{_periodo(filtro)}: {montos}."


def _formatear_cantidad(filtro: BaseModel, filas: Sequence[FilaCalculo]) -> str:
    if not filas:
        return f"No hay facturas confirmadas{_periodo(filtro)}."
    cantidad = sum(fila["cantidad"] for fila in filas)
    return f"Facturas confirmadas{_periodo(filtro)}: {cantidad}."


def _formatear_por_emisor(filtro: BaseModel, filas: Sequence[FilaCalculo]) -> str:
    if not filas:
        return f"No hay facturas confirmadas{_periodo(filtro)}."
    lineas = "; ".join(
        f"{fila['emisor']}: {_monto(fila['total'], fila['moneda'])} ({_facturas(fila['cantidad'])})"
        for fila in filas
    )
    return f"Facturado por emisor{_periodo(filtro)}: {lineas}."


def _formatear_mas_alta(filtro: BaseModel, filas: Sequence[FilaCalculo]) -> str:
    if not filas:
        return f"No hay facturas confirmadas{_periodo(filtro)}."
    # Una por moneda: comparar montos de monedas distintas no tiene sentido.
    por_moneda = "; ".join(
        f"N° {fila['numero']} de {fila['emisor']}, del {fila['fecha'].isoformat()}, "
        f"por {_monto(fila['total'], fila['moneda'])}"
        for fila in filas
    )
    return f"Factura más alta por moneda{_periodo(filtro)}: {por_moneda}."


FACTURAS = PaqueteDominio(
    nombre=NOMBRE,
    descripcion="Facturas: folio, fecha, emisor, receptor, montos y detalle.",
    esquema=Factura,
    texto_para_embeber=texto_para_embeber,
    herramientas=(
        HerramientaSQL(
            nombre="total_facturado",
            descripcion="Suma de los totales por moneda (opcional: período, emisor).",
            argumentos=FiltroFacturas,
            sql=SQL_TOTAL,
            formatear=_formatear_total,
        ),
        HerramientaSQL(
            nombre="cantidad_de_facturas",
            descripcion="Cuántas facturas hay (opcional: período y emisor).",
            argumentos=FiltroFacturas,
            sql=SQL_TOTAL,
            formatear=_formatear_cantidad,
        ),
        HerramientaSQL(
            nombre="facturado_por_emisor",
            descripcion="Ranking de emisores por monto, por moneda (opcional: período, límite).",
            argumentos=FiltroPorEmisor,
            sql=SQL_POR_EMISOR,
            formatear=_formatear_por_emisor,
        ),
        HerramientaSQL(
            nombre="factura_mas_alta",
            descripcion="La factura de mayor total de cada moneda (opcional: período, emisor).",
            argumentos=FiltroFacturas,
            sql=SQL_MAS_ALTA,
            formatear=_formatear_mas_alta,
        ),
    ),
)
