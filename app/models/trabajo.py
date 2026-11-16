from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constantes import EstadoTrabajo, TipoTrabajo
from app.config.database import Base
from app.models.coleccion import Coleccion
from app.models.mixins import ConCreadoEn


class Trabajo(ConCreadoEn, Base):
    """Ingesta en segundo plano. El avance son contadores que el worker suma de a uno (UPDATE
    atómico); el estado se deriva de ellos en vez de guardarse aparte."""

    __tablename__ = "trabajo"

    id: Mapped[int] = mapped_column(primary_key=True)
    coleccion_id: Mapped[int] = mapped_column(
        ForeignKey("coleccion.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[TipoTrabajo] = mapped_column(
        Enum(TipoTrabajo, name="tipo_trabajo", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    # None mientras no se sabe (una sincronización lo conoce al leer la fuente).
    total: Mapped[int | None] = mapped_column(nullable=True)
    ingeridos: Mapped[int] = mapped_column(nullable=False, server_default="0")
    duplicados: Mapped[int] = mapped_column(nullable=False, server_default="0")
    sin_cambios: Mapped[int] = mapped_column(nullable=False, server_default="0")
    rechazados: Mapped[int] = mapped_column(nullable=False, server_default="0")
    errores: Mapped[int] = mapped_column(nullable=False, server_default="0")
    eliminados: Mapped[int] = mapped_column(nullable=False, server_default="0")
    trozos: Mapped[int] = mapped_column(nullable=False, server_default="0")
    ultimo_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    coleccion: Mapped[Coleccion] = relationship()

    @property
    def procesados(self) -> int:
        return self.ingeridos + self.duplicados + self.sin_cambios + self.rechazados + self.errores

    @property
    def estado(self) -> EstadoTrabajo:
        if self.total is not None and self.procesados >= self.total:
            return EstadoTrabajo.TERMINADO
        if self.procesados > 0:
            return EstadoTrabajo.EN_CURSO
        return EstadoTrabajo.PENDIENTE
