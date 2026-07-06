from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os, shutil, mimetypes, uuid
from database import get_db
import models, schemas

router = APIRouter(prefix="/documents", tags=["Documents"])

UPLOAD_DIR = "uploads/documents"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/", response_model=List[schemas.DocumentOut])
def list_documents(project_id: Optional[int] = None, doc_type: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.Document)
    if project_id:
        q = q.filter(models.Document.project_id == project_id)
    if doc_type:
        q = q.filter(models.Document.doc_type == doc_type)
    return q.order_by(models.Document.created_at.desc()).all()


@router.post("/", response_model=schemas.DocumentOut, status_code=201)
def create_document(data: schemas.DocumentCreate, db: Session = Depends(get_db)):
    doc = models.Document(**data.model_dump())
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.post("/upload", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    project_id: Optional[str] = Form(None),
    doc_type: Optional[str] = Form("blueprint"),
    version: str = Form("1.0"),
    uploaded_by: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    # Unique filename to avoid collisions
    ext = os.path.splitext(file.filename)[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    doc = models.Document(
        title=title,
        project_id=int(project_id) if project_id and project_id.isdigit() else None,
        doc_type=doc_type,
        file_name=file.filename,
        file_path=file_path,
        version=version,
        uploaded_by=uploaded_by,
        description=description,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "file_name": doc.file_name, "title": doc.title}


@router.get("/{doc_id}/download")
def download_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="File not found on server")
    mime, _ = mimetypes.guess_type(doc.file_name or doc.file_path)
    return FileResponse(
        path=doc.file_path,
        filename=doc.file_name or os.path.basename(doc.file_path),
        media_type=mime or "application/octet-stream"
    )


@router.get("/{doc_id}", response_model=schemas.DocumentOut)
def get_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)
    db.delete(doc)
    db.commit()
    return {"message": "Deleted"}
