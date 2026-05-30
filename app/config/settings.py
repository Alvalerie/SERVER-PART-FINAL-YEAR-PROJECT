from pydantic_settings import BaseSettings, SettingsConfigDict


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


settings = Settings()