# Import all models here so Alembic's autogenerate can detect them via Base.metadata
from app.models.item import Item  # noqa: F401

__all__ = ["Item"]
