from app.auth.otp_service import generate_otp
from app.auth.jwt_handler import create_token
from app.database import SessionLocal
from app.models import User, OTP

