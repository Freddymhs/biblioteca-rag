from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constantes import MAX_LARGO_NOMBRE, MAX_LARGO_SLUG
from app.config.database import Base
from app.models.mixins import ConCreadoEn

if TYPE_CHECKING:
    from app.models.coleccion import Coleccion


class Espacio(ConCreadoEn, Base):
    """Área de vida (intereses, personal, estudios). Una pregunta puede abarcar todo un espacio."""

    __tablename__ = "espacio"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(MAX_LARGO_SLUG), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(MAX_LARGO_NOMBRE), nullable=False)

    colecciones: Mapped[list["Coleccion"]] = relationship(back_populates="espacio")
