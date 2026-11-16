from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constantes import MAX_LARGO_NOMBRE, MAX_LARGO_SLUG
from app.config.database import Base
from app.models.mixins import ConCreadoEn

if TYPE_CHECKING:
    from app.models.documento import Documento
    from app.models.espacio import Espacio


class Coleccion(ConCreadoEn, Base):
    """Biblioteca temática dentro de un espacio (agricultura, cocina...). Es data, no código."""

    __tablename__ = "coleccion"
    __table_args__ = (
        UniqueConstraint("espacio_id", "slug", name="uq_coleccion_espacio_slug"),
        # G13: sus datos (facturas, etc.) nunca se publican.
        CheckConstraint(
            "NOT (publica AND paquete IS NOT NULL)", name="ck_coleccion_paquete_no_publica"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    espacio_id: Mapped[int] = mapped_column(
        ForeignKey("espacio.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(MAX_LARGO_SLUG), nullable=False)
    nombre: Mapped[str] = mapped_column(String(MAX_LARGO_NOMBRE), nullable=False)
    # Paquete de dominio (ej. «facturas»): sus documentos pasan por extracción y confirmación.
    paquete: Mapped[str | None] = mapped_column(String(MAX_LARGO_SLUG), nullable=True)
    # Pública: la leen la API pública y el MCP (rol `biblioteca_publico`, RLS). Por defecto, no.
    publica: Mapped[bool] = mapped_column(nullable=False, server_default=false())

    espacio: Mapped["Espacio"] = relationship(back_populates="colecciones")
    documentos: Mapped[list["Documento"]] = relationship(back_populates="coleccion")
