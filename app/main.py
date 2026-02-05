# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from app.routers import auth, upload, analytics

# 1️⃣ Create the FastAPI app instance
app = FastAPI(
    title="CDR Intelligence API",
    description="API for CDR analysis, secure uploads, and intelligence generation",
    version="1.0.0"
)

# 2️⃣ Optional: Add CORS middleware if your frontend is separate
origins = [
    "http://localhost",
    "http://localhost:3000",  # React/Vue frontend
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3️⃣ Include your routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])         # /auth/login, /auth/register
app.include_router(upload.router, prefix="/upload", tags=["File Upload"])       # /upload/file
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])  # /analytics/generate

# 4️⃣ Root endpoint (optional)
@app.get("/")
def root():
    return {"message": "Welcome to the CDR Intelligence API"}
