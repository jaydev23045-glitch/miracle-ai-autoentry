import os
import sys
import warnings
import logging

# Suppress google-genai SDK automatic function calling (AFC) recommendation warnings
warnings.filterwarnings("ignore", category=UserWarning, message=".*Automatic function calling.*")
warnings.filterwarnings("ignore", category=UserWarning, message=".*automatic function calling.*")
warnings.filterwarnings("ignore", message=".*Automatic function calling.*")
warnings.filterwarnings("ignore", message=".*automatic function calling.*")

logging.getLogger("google.genai").setLevel(logging.ERROR)
logging.getLogger("google.generativeai").setLevel(logging.ERROR)

# Ensure pandas & Excel dependencies from backend/venv site-packages are in sys.path
try:
    import pandas as pd
except ImportError:
    py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
    base_venv_lib = os.path.abspath(os.path.join(os.path.dirname(__file__), "venv", "lib"))
    backend_venv_sp = os.path.join(base_venv_lib, py_ver, "site-packages")
    if not os.path.exists(backend_venv_sp) and os.path.exists(base_venv_lib):
        for item in os.listdir(base_venv_lib):
            if item.startswith("python3"):
                candidate = os.path.join(base_venv_lib, item, "site-packages")
                if os.path.exists(candidate):
                    backend_venv_sp = candidate
                    break
    if os.path.exists(backend_venv_sp) and backend_venv_sp not in sys.path:
        sys.path.insert(0, backend_venv_sp)

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers.settings import router as settings_router
from routers.vouchers import router as vouchers_router

app = FastAPI(title="Miracle AI Auto-Entry API")

# Allow frontend to access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local network access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    # Ensure browsers NEVER cache index.html or app.js after server updates
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0, post-check=0, pre-check=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/health")
def health_check():
    return {
        "status": "online",
        "service": "Miracle AI Server",
        "mode": "cloud_server"
    }

# Include separated routers
app.include_router(settings_router)
app.include_router(vouchers_router)

# Mount frontend static files
frontend_candidates = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../frontend"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend"),
    os.path.join(os.getcwd(), "frontend"),
    os.path.join(getattr(sys, "_MEIPASS", os.getcwd()), "frontend")
]
frontend_path = next((p for p in frontend_candidates if os.path.exists(p)), frontend_candidates[0])
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    # Runs on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
