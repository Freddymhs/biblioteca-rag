# Registro único de modelos: Alembic autogenerate solo ve lo que se importa aquí (ver CLAUDE.md).
from app.models.coleccion import Coleccion
from app.models.documento import Documento
from app.models.espacio import Espacio
from app.models.trabajo import Trabajo
from app.models.trozo import Trozo

__all__ = ["Coleccion", "Documento", "Espacio", "Trabajo", "Trozo"]
