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

    # Refresh token — separate secret so a leaked access secret
    # cannot be used to forge refresh tokens and vice versa
    REFRESH_SECRET_KEY: str = "change-refresh-secret-in-production"
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

     # Image storage
    IMAGES_DIR: Path = BASE_DIR / "images" 

    # Handwriting sample quality
    # Served to the mobile app via GET /config/sample-quality so both
    # sides enforce the same numbers and cannot drift apart.
    MIN_SAMPLE_WIDTH: int = 150
    MIN_SAMPLE_HEIGHT: int = 150
    MAX_SAMPLE_ASPECT_RATIO: float = 4.0
    MIN_SAMPLE_BLUR_SCORE: float = 100.0      # placeholder, calibrate first
    MIN_SAMPLE_CONTRAST: float = 30.0
    MIN_SAMPLE_INK_RATIO: float = 0.01
    MAX_SAMPLE_INK_RATIO: float = 0.50

    # Server is slightly more permissive than what it advertises, so a
    # borderline image the app accepted is never rejected on upload.
    SERVER_QUALITY_TOLERANCE: float = 0.9

    # Reject blur outright, or log and let through? Keep False until the
    # threshold is calibrated on real images.
    ENFORCE_BLUR_CHECK: bool = False

    MODEL_CHECKPOINT_PATH: Path = BASE_DIR / "ml" / "best_model.pth"

    # A student below this is not considered enrolled.
    MIN_SAMPLES_PER_STUDENT: int = 10

    # Mark OCR confidence required before auto_confirm_exact will write a
    # mark unseen. High, because this is the unreviewed path.
    OCR_MARK_AUTOCONFIRM_CONF: float = 0.90

    # Embeddings from different checkpoints are not comparable.
    MODEL_VERSION: str = "siamese-resnet18-v1"


settings = Settings()

# Ensure the images folder always exists at startup
settings.IMAGES_DIR.mkdir(parents=True, exist_ok=True)