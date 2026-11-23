from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, Enum, FetchedValue, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constantes import (
    DIMENSION_EMBEDDING,
    HNSW_EF_CONSTRUCTION,
    HNSW_M,
    MAX_LARGO_MODELO_EMBEDDING,
    OrigenTrozo,
)
from app.config.database import Base
from app.models.mixins import ConCreadoEn

if TYPE_CHECKING:
    from app.models.documento import Documento


class Trozo(ConCreadoEn, Base):
    """Fragmento citable. Guarda el texto original y qué modelo lo embebió: así se re-embebe
    sin volver a extraer, y una búsqueda nunca mezcla vectores de dos modelos."""

    __tablename__ = "trozo"
    __table_args__ = (
        CheckConstraint("pagina_fin >= pagina_inicio", name="ck_trozo_rango_paginas"),
        Index(
            "ix_trozo_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": HNSW_M, "ef_construction": HNSW_EF_CONSTRUCTION},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    documento_id: Mapped[int] = mapped_column(
        ForeignKey("documento.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 6.3: copia de la ubicación del documento, en la tabla del índice HNSW: el filtro por espacio o
    # colección va en el recorrido del índice. Los completa un trigger de la base (migración
    # b1e6f3a9d250): el código no los escribe, y no pueden contradecir al documento.
    espacio_id: Mapped[int] = mapped_column(
        ForeignKey("espacio.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        server_default=FetchedValue(),
    )
    coleccion_id: Mapped[int] = mapped_column(
        ForeignKey("coleccion.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        server_default=FetchedValue(),
    )
    orden: Mapped[int] = mapped_column(nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    # Rango de páginas del trozo (iguales si cabe en una). None en texto plano.
    pagina_inicio: Mapped[int | None] = mapped_column(nullable=True)
    pagina_fin: Mapped[int | None] = mapped_column(nullable=True)
    origen: Mapped[OrigenTrozo] = mapped_column(
        Enum(OrigenTrozo, name="origen_trozo", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        server_default=OrigenTrozo.TEXTO.value,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(DIMENSION_EMBEDDING), nullable=False)
    embedding_model: Mapped[str] = mapped_column(
        String(MAX_LARGO_MODELO_EMBEDDING), nullable=False, index=True
    )

    documento: Mapped["Documento"] = relationship(back_populates="trozos")
