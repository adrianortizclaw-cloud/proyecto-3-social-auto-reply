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
    frontend_origin: str = "http://localhost:5173"
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_redirect_uri: str = "http://localhost:8000/api/meta/oauth/callback"
    meta_scopes_csv: str = "instagram_business_basic,instagram_business_content_publish,instagram_business_manage_messages,instagram_business_manage_comments"
    meta_webhook_verify_token: str = "dev-meta-webhook-token"

    @field_validator("app_secret_key")
    @classmethod
    def validate_secret_key(cls, v: str):
        if len(v) < 16:
            raise ValueError("APP_SECRET_KEY too short")
        return v

    @property
    def meta_scopes(self) -> list[str]:
        return [s.strip() for s in self.meta_scopes_csv.split(",") if s.strip()]

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
