from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent 


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5433/db_name"

    # App
    APP_NAME: str = "AI Capturing API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = "gtdzswervchuolkmnbvccfxxjhrewqaxessaazz"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

     # Image storage
    IMAGES_DIR: Path = BASE_DIR / "images"


settings = Settings()

# Ensure the images folder always exists at startup
settings.IMAGES_DIR.mkdir(parents=True, exist_ok=True)