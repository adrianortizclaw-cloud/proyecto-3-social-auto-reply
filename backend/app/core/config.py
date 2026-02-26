from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    app_name: str = "social-auto-reply"
    database_url: str
    redis_url: str
    jwt_secret: str
    jwt_expire_minutes: int = 60
    app_secret_key: str
    cors_origins: str = "http://localhost:5173"

    @field_validator("app_secret_key")
    @classmethod
    def validate_secret_key(cls, v: str):
        if len(v) < 16:
            raise ValueError("APP_SECRET_KEY too short")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
