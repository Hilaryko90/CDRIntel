from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.analytics import analyze_cdr
from app.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/generate")
def generate_intelligence(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    intel = analyze_cdr(db)
    return {"message": "Intelligence generated", "data": intel}
