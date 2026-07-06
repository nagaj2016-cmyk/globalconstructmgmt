from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
import models, schemas

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("/", response_model=List[schemas.InventoryOut])
def list_inventory(category: Optional[str] = None, low_stock: Optional[bool] = None, db: Session = Depends(get_db)):
    q = db.query(models.InventoryItem)
    if category:
        q = q.filter(models.InventoryItem.category == category)
    if low_stock:
        q = q.filter(models.InventoryItem.quantity <= models.InventoryItem.min_quantity)
    return q.order_by(models.InventoryItem.name).all()


@router.post("/", response_model=schemas.InventoryOut, status_code=201)
def create_item(data: schemas.InventoryCreate, db: Session = Depends(get_db)):
    item = models.InventoryItem(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{item_id}", response_model=schemas.InventoryOut)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.InventoryItem).filter(models.InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.put("/{item_id}", response_model=schemas.InventoryOut)
def update_item(item_id: int, data: schemas.InventoryUpdate, db: Session = Depends(get_db)):
    item = db.query(models.InventoryItem).filter(models.InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{item_id}/adjust")
def adjust_stock(item_id: int, quantity_change: float, db: Session = Depends(get_db)):
    item = db.query(models.InventoryItem).filter(models.InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item.quantity = max(0, (item.quantity or 0) + quantity_change)
    db.commit()
    return {"id": item_id, "new_quantity": item.quantity}


@router.delete("/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.InventoryItem).filter(models.InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"message": "Deleted"}
