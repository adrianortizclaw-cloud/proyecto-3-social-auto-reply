from pydantic import BaseModel, Field


class SocialAccountCreate(BaseModel):
    platform: str = Field(pattern="^(instagram|facebook|x)$")
    account_handle: str
    prompt_persona: str
    instagram_token: str | None = None
    openai_api_key: str | None = None
    auto_mode: str = Field(default="semi_auto", pattern="^(auto|semi_auto|manual)$")


class SocialAccountOut(BaseModel):
    id: int
    platform: str
    account_handle: str
    prompt_persona: str
    auto_mode: str
    connected: bool

    class Config:
        from_attributes = True
