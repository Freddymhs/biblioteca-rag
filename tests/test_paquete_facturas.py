from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.dominio import PAQUETES, obtener_paquete
from app.dominio.facturas import Factura, texto_para_embeber
from tests.dobles import FACTURA_OLIVOS


def test_fecha_fuera_de_rango_no_valida() -> None:
    """Lo que leyó llama3.2:3b de «12-03-2026»: el año 1203, una fecha válida para Python."""
    with pytest.raises(ValidationError, match="1203"):
        Factura.model_validate({**FACTURA_OLIVOS, "fecha": "1203-03-26"})


def test_montos_negativos_no_validan() -> None:
    with pytest.raises(ValidationError):
        Factura.model_validate({**FACTURA_OLIVOS, "total": "-1"})


def test_texto_para_embeber_lleva_los_datos_confirmados() -> None:
    factura = Factura.model_validate(FACTURA_OLIVOS)

    texto = texto_para_embeber(factura)

    assert texto.startswith("Factura N° 4521 del 2026-03-12")
    assert "Agricola Los Olivos SpA" in texto
    assert "119.000 CLP" in texto
    assert factura.fecha == date(2026, 3, 12) and factura.total == Decimal("119000")


def test_el_registro_resuelve_por_nombre() -> None:
    assert obtener_paquete("facturas") is PAQUETES["facturas"]
    nombres = [h.nombre for h in PAQUETES["facturas"].herramientas]
    assert nombres == [
        "total_facturado",
        "cantidad_de_facturas",
        "facturado_por_emisor",
        "factura_mas_alta",
    ]
