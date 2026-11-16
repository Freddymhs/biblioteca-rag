from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint, false
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constantes import (
    LARGO_SHA256_HEX,
    MAX_LARGO_ID_EXTERNO,
    MAX_LARGO_LICENCIA,
    MAX_LARGO_NOMBRE_ARCHIVO,
    TipoDocumento,
)
from app.config.database import Base
from app.models.mixins import ConCreadoEn

if TYPE_CHECKING:
    from app.models.coleccion import Coleccion
    from app.models.extraccion import Extraccion
    from app.models.trozo import Trozo


class Documento(ConCreadoEn, Base):
    """Archivo ingerido. El hash de contenido impide ingerir dos veces el mismo en una colección."""

    __tablename__ = "documento"
    __table_args__ = (
        UniqueConstraint("coleccion_id", "hash_contenido", name="uq_documento_coleccion_hash"),
        # NULL no choca con NULL en Postgres: los archivos subidos no llevan id externo.
        UniqueConstraint("coleccion_id", "id_externo", name="uq_documento_coleccion_id_externo"),
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

    # DoclingDocument serializado: re-trocear sin volver a extraer. None en documentos anteriores.
    # `Any`: es el JSON que define Docling, no un esquema propio.
    estructura: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # Id del registro en la fuente de un conector (ej. «work:SIIGSA»). None en archivos subidos.
    id_externo: Mapped[str | None] = mapped_column(String(MAX_LARGO_ID_EXTERNO), nullable=True)
    # Licencia declarada (ej. «CC BY-NC-SA 4.0»). Un documento es público solo si su colección
    # lo es Y una persona verificó la licencia; sin verificar, nunca (DECISION_SERVICIO_PUBLICO).
    licencia: Mapped[str | None] = mapped_column(String(MAX_LARGO_LICENCIA), nullable=True)
    licencia_verificada: Mapped[bool] = mapped_column(nullable=False, server_default=false())

    coleccion: Mapped["Coleccion"] = relationship(back_populates="documentos")
    # Solo en colecciones con paquete de dominio; se guarda y se borra con el documento.
    extraccion: Mapped["Extraccion | None"] = relationship(
        back_populates="documento", cascade="all, delete-orphan", passive_deletes=True
    )
    trozos: Mapped[list["Trozo"]] = relationship(
        back_populates="documento", cascade="all, delete-orphan", passive_deletes=True
    )
