from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models, schemas

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.get("/", response_model=List[schemas.ClientOut])
def list_clients(db: Session = Depends(get_db)):
    return db.query(models.Client).order_by(models.Client.name).all()


@router.post("/", response_model=schemas.ClientOut, status_code=201)
def create_client(data: schemas.ClientCreate, db: Session = Depends(get_db)):
    c = models.Client(**data.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.get("/{client_id}", response_model=schemas.ClientOut)
def get_client(client_id: int, db: Session = Depends(get_db)):
    c = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    return c


@router.put("/{client_id}", response_model=schemas.ClientOut)
def update_client(client_id: int, data: schemas.ClientUpdate, db: Session = Depends(get_db)):
    c = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/{client_id}")
def delete_client(client_id: int, db: Session = Depends(get_db)):
    c = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    db.delete(c)
    db.commit()
    return {"message": "Deleted"}
