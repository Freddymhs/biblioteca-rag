from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constantes import LARGO_SHA256_HEX, MAX_LARGO_NOMBRE_ARCHIVO, TipoDocumento
from app.config.database import Base
from app.models.mixins import ConCreadoEn

if TYPE_CHECKING:
    from app.models.coleccion import Coleccion
    from app.models.trozo import Trozo


class Documento(ConCreadoEn, Base):
    """Archivo ingerido. El hash de contenido impide ingerir dos veces el mismo en una colección."""

    __tablename__ = "documento"
    __table_args__ = (
        UniqueConstraint("coleccion_id", "hash_contenido", name="uq_documento_coleccion_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    coleccion_id: Mapped[int] = mapped_column(
        ForeignKey("coleccion.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    nombre_archivo: Mapped[str] = mapped_column(String(MAX_LARGO_NOMBRE_ARCHIVO), nullable=False)
    hash_contenido: Mapped[str] = mapped_column(String(LARGO_SHA256_HEX), nullable=False)
    tipo: Mapped[TipoDocumento] = mapped_column(
        Enum(TipoDocumento, name="tipo_documento", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    # None en formatos sin páginas (texto plano).
    paginas: Mapped[int | None] = mapped_column(nullable=True)

    coleccion: Mapped["Coleccion"] = relationship(back_populates="documentos")
    trozos: Mapped[list["Trozo"]] = relationship(
        back_populates="documento", cascade="all, delete-orphan", passive_deletes=True
    )
