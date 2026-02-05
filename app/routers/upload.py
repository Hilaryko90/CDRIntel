from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Upload
from app.ingestion.validators import validate_file
from app.security import get_current_user
from datetime import datetime
import os, uuid

router = APIRouter(prefix="/upload", tags=["Secure Upload"])

RAW_DIR = "app/storage/raw"

@router.post("/")
def upload_file(
    case_id: str,
    purpose: str,
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    db: Session = SessionLocal()

    temp_name = f"{uuid.uuid4()}_{file.filename}"
    temp_path = os.path.join(RAW_DIR, temp_name)

    # Save temporarily
    with open(temp_path, "wb") as f:
        content = file.file.read()
        validate_file(file.filename, len(content))
        f.write(content)

    from app.ingestion.hashing import sha256_file
    sha256 = sha256_file(temp_path)

    # Prevent duplicate evidence
    if db.query(Upload).filter(Upload.sha256 == sha256).first():
        os.remove(temp_path)
        raise HTTPException(status_code=409, detail="Duplicate evidence")

    record = Upload(
        filename=file.filename,
        stored_path=temp_path,
        sha256=sha256,
        uploader=user["username"],
        case_id=case_id,
        purpose=purpose
    )

    db.add(record)
    db.commit()

    # Make RAW file READ-ONLY
    os.chmod(temp_path, 0o444)

    return {
        "message": "File uploaded securely",
        "sha256": sha256,
        "case_id": case_id
    }
