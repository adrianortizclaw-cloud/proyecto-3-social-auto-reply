from __future__ import annotations

from urllib.parse import urlencode

import httpx

from app.core.config import settings


class InstagramError(Exception):
    """Any error from the Instagram Graph API."""


BASE_URL = f"https://graph.instagram.com/{settings.instagram_graph_version}"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _handle(resp: httpx.Response) -> dict:
    if resp.status_code >= 400:
        raise InstagramError(f"[{resp.status_code}] {resp.text}")
    return resp.json()


def get_login_url(permissions: list[str] | None = None, state: str = "") -> str:
    perms = permissions or [
        "instagram_business_basic",
        "instagram_business_manage_comments",
    ]
    params = {
        "client_id": settings.instagram_app_id,
        "redirect_uri": settings.instagram_callback_url,
        "scope": ",".join(perms),
        "response_type": "code",
        "enable_fb_login": 0,
        "force_authentication": 1,
    }
    if state:
        params["state"] = state
    return f"https://www.instagram.com/oauth/authorize?{urlencode(params)}"


def get_user_info(token: str, fields: str = "id,name,username") -> dict:
    resp = httpx.get(
        "https://graph.instagram.com/me",
        params={"fields": fields, "access_token": token},
        timeout=20,
    )
    return _handle(resp)


def exchange_code_for_token(code: str) -> dict:
    short_resp = httpx.post(
        "https://api.instagram.com/oauth/access_token",
        data={
            "client_id": settings.instagram_app_id,
            "client_secret": settings.instagram_app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": settings.instagram_callback_url,
            "code": code,
        },
        timeout=20,
    )
    short = _handle(short_resp)

    long_resp = httpx.get(
        "https://graph.instagram.com/access_token",
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": settings.instagram_app_secret,
            "access_token": short["access_token"],
        },
        timeout=20,
    )
    long_lived = _handle(long_resp)

    user = get_user_info(long_lived["access_token"])
    return {**long_lived, **user}


def refresh_token(token: str) -> dict:
    resp = httpx.get(
        "https://graph.instagram.com/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
        timeout=20,
    )
    return _handle(resp)


class Instagram:
    def __init__(self, token: str):
        self.token = token

    def get(self, endpoint: str, params: dict | None = None) -> dict:
        resp = httpx.get(
            f"{BASE_URL}{endpoint}",
            headers=_headers(self.token),
            params=params or {},
            timeout=20,
        )
        return _handle(resp)

    def post(self, endpoint: str, data: dict | None = None) -> dict:
        resp = httpx.post(
            f"{BASE_URL}{endpoint}",
            headers={**_headers(self.token), "Content-Type": "application/json"},
            json=data or {},
            timeout=20,
        )
        return _handle(resp)

    def delete(self, endpoint: str) -> dict:
        resp = httpx.delete(
            f"{BASE_URL}{endpoint}",
            headers=_headers(self.token),
            timeout=20,
        )
        return _handle(resp)

    def me(self, fields: str = "id,name,username") -> dict:
        return self.get("/me", {"fields": fields})

    def get_media(self, fields: str = "id,caption,timestamp,media_url,permalink") -> dict:
        return self.get("/me/media", {"fields": fields})

    def get_comments(self, media_id: str, fields: str = "id,text,username,timestamp") -> dict:
        return self.get(f"/{media_id}/comments", {"fields": fields})

    def get_comment(self, comment_id: str, fields: str = "id,text,timestamp") -> dict:
        return self.get(f"/{comment_id}", {"fields": fields})

    def get_replies(self, comment_id: str, fields: str = "id,text,username,timestamp") -> dict:
        return self.get(f"/{comment_id}/replies", {"fields": fields})

    def add_comment(self, media_id: str, message: str) -> dict:
        return self.post(f"/{media_id}/comments", {"message": message})

    def reply_to_comment(self, comment_id: str, message: str) -> dict:
        return self.post(f"/{comment_id}/replies", {"message": message})

    def delete_comment(self, comment_id: str) -> dict:
        return self.delete(f"/{comment_id}")

    def hide_comment(self, comment_id: str, hide: bool = True) -> dict:
        return self.post(f"/{comment_id}", {"hide": hide})
