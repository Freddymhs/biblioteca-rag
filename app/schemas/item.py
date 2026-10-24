from datetime import datetime
from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    """Input schema — equivalent to a Zod schema for request body."""

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ItemUpdate(BaseModel):
    """Partial update — all fields optional (like Zod .partial())."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class ItemResponse(BaseModel):
    """Output schema — what the API returns."""

    id: int
    title: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}  # allows building from SQLAlchemy models
