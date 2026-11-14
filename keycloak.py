import os
from pathlib import Path
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
SECRET_KEY = os.getenv("SECRET_KEY", "unsafe-development-secret-change-me-please-32chars")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")
ADMIN_USERNAME = os.getenv("INITIAL_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD", "ChangeThis-Immediately-123!")
CORS_ORIGINS = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:8080,http://localhost:5173").split(",") if x.strip()]
