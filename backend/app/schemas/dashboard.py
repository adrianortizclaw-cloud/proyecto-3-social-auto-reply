from pydantic import BaseModel


class DashboardItem(BaseModel):
    id: str
    text: str
    created_at: str


class DashboardResponse(BaseModel):
    latest_posts: list[DashboardItem]
    latest_reels: list[DashboardItem]
    latest_comments: list[DashboardItem]
    latest_replies: list[DashboardItem]
