# app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from app.api.routes import router

# Create FastAPI app
app = FastAPI(title="IMU Recording System")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get the directory where main.py is located
BASE_DIR = Path(__file__).resolve().parent

# Mount static files directory
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Include API routes
app.include_router(router, prefix="/api")

# Root endpoint to serve index.html
@app.get("/")
async def read_root():
    return FileResponse(BASE_DIR / "static" / "index.html")
