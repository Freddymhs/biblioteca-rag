"""Uso de lo público (tarea 5.2). Privado: va en el grupo que exige la API key (`main.py`)."""

from fastapi import APIRouter, Depends, Query

from app.config.constantes import DIAS_USO_POR_DEFECTO, RETENCION_USO_DIAS
from app.providers.limites import Limitador, obtener_limitador
from app.schemas.uso import RechazosSalida, UsoDelDiaSalida

router = APIRouter(prefix="/uso", tags=["uso público"])


@router.get("", response_model=list[UsoDelDiaSalida])
def uso_publico(
    dias: int = Query(default=DIAS_USO_POR_DEFECTO, ge=1, le=RETENCION_USO_DIAS),
    limitador: Limitador = Depends(obtener_limitador),
) -> list[UsoDelDiaSalida]:
    """Consultas públicas servidas y 429 emitidos por día, de hoy hacia atrás."""
    return [
        UsoDelDiaSalida(
            fecha=dia.fecha,
            busquedas=dia.busquedas,
            respuestas=dia.respuestas,
            rechazos_429=RechazosSalida(
                busqueda=dia.rechazos_busqueda, respuesta=dia.rechazos_respuesta
            ),
        )
        for dia in limitador.leer_uso(dias)
    ]
