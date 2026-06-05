# config.py
import os
from dotenv import load_dotenv

load_dotenv()   # ← reads your .env file automatically

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-only-for-dev")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── JWT ──
    JWT_SECRET_KEY   = os.getenv("JWT_SECRET_KEY", "change-this-secret")
    #JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", 24))
    JWT_EXPIRY_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", 30))
    JSON_SORT_KEYS = False
