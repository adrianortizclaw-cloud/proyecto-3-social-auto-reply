from pydantic import BaseModel, Field


class SocialAccountCreate(BaseModel):
    platform: str = Field(pattern="^(instagram|facebook|x)$")
    account_handle: str
    prompt_persona: str
    instagram_token: str | None = None
    openai_api_key: str | None = None


class SocialAccountOut(BaseModel):
    id: int
    platform: str
    account_handle: str
    prompt_persona: str

    class Config:
        from_attributes = True
