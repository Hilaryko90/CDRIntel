from fastapi import APIRouter, HTTPException
from app.auth.otp_service import generate_otp
from app.auth.jwt_handler import create_token

router = APIRouter()


@router.post("/login")
def login(user_id: int):
    otp = generate_otp(user_id)
    token = create_token({"sub": str(user_id)})
    return {
        "otp": otp,
        "access_token": token
    }
