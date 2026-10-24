from sqlalchemy.orm import Session
from app.models.item import Item
from app.schemas.item import ItemCreate, ItemUpdate
from app.common.errors import not_found


def get_all(db: Session) -> list[Item]:
    return db.query(Item).order_by(Item.created_at.desc()).all()


def get_by_id(db: Session, item_id: int) -> Item:
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise not_found("Item")
    return item


def create(db: Session, data: ItemCreate) -> Item:
    item = Item(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update(db: Session, item_id: int, data: ItemUpdate) -> Item:
    item = get_by_id(db, item_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def delete(db: Session, item_id: int) -> None:
    item = get_by_id(db, item_id)
    db.delete(item)
    db.commit()
