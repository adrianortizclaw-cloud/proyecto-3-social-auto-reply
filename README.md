# Proyecto 3 — Instagram Wrapper (Backend + Frontend + DB)

Rebuild del proyecto con la misma base (frontend + backend + PostgreSQL en Docker Compose), centrado en un wrapper limpio de la API de Instagram Business.

## Stack
- **Frontend:** React + Vite
- **Backend:** FastAPI + SQLAlchemy + httpx
- **DB:** PostgreSQL
- **Infra:** Docker Compose

## Arranque
```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend docs: http://localhost:8000/docs

## Variables de entorno (`.env`)
Asegúrate de tener al menos:

```env
POSTGRES_DB=socialbot
POSTGRES_USER=socialbot
POSTGRES_PASSWORD=socialbot123
DATABASE_URL=postgresql+psycopg://socialbot:socialbot123@db:5432/socialbot
REDIS_URL=redis://redis:6379/0
JWT_SECRET=dev-jwt-secret
APP_SECRET_KEY=dev-very-secret-key-for-encryption-123456
CORS_ORIGINS=http://localhost:5173
FRONTEND_ORIGIN=http://localhost:5173

INSTAGRAM_APP_ID=...
INSTAGRAM_APP_SECRET=...
INSTAGRAM_CALLBACK_URL=http://localhost:8000/api/instagram/callback
INSTAGRAM_GRAPH_VERSION=v21.0
```

## Flujo funcional
1. Frontend muestra una tarjeta central **Login with Instagram**.
2. Backend genera la URL OAuth (`GET /api/instagram/login-url`).
3. Instagram redirige al callback del backend (`GET /api/instagram/callback`).
4. Backend intercambia `code -> token`, crea sesión en DB y redirige al frontend con `?session=...`.
5. Frontend muestra una pantalla de utilidades en grid: botón + respuesta JSON.

## Endpoints principales
- `GET /api/instagram/login-url`
- `GET /api/instagram/callback`
- `GET /api/instagram/session`
- `GET /api/instagram/me`
- `GET /api/instagram/media`
- `GET /api/instagram/comments/{media_id}`
- `GET /api/instagram/comment/{comment_id}`
- `GET /api/instagram/replies/{comment_id}`
- `POST /api/instagram/comments/{media_id}`
- `POST /api/instagram/reply/{comment_id}`
- `POST /api/instagram/comments/{comment_id}/visibility`
- `DELETE /api/instagram/comments/{comment_id}`
- `POST /api/instagram/raw`

Todos los endpoints protegidos usan header `X-Session-Id`.
