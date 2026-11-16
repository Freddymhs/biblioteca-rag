from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constantes import MAX_LARGO_SLUG, EstadoExtraccion
from app.config.database import Base
from app.models.mixins import ConCreadoEn

if TYPE_CHECKING:
    from app.models.documento import Documento


class Extraccion(ConCreadoEn, Base):
    """Datos estructurados de un documento de una colección con paquete de dominio.

    `propuesta` es lo que leyó el LLM (puede no validar: `errores` dice por qué). Solo
    `confirmados`, escritos por una persona y validados contra el esquema, se embeben y los ven
    las herramientas SQL.
    """

    __tablename__ = "extraccion"

    id: Mapped[int] = mapped_column(primary_key=True)
    documento_id: Mapped[int] = mapped_column(
        ForeignKey("documento.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    paquete: Mapped[str] = mapped_column(String(MAX_LARGO_SLUG), nullable=False)
    estado: Mapped[EstadoExtraccion] = mapped_column(
        Enum(
            EstadoExtraccion,
            name="estado_extraccion",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    # `Any`: JSON del esquema del paquete; su forma la valida el modelo Pydantic del paquete.
    propuesta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    errores: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    confirmados: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    confirmado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    documento: Mapped["Documento"] = relationship(back_populates="extraccion")
