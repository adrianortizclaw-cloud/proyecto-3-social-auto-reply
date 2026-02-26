# Social Auto-Reply Dashboard (Proyecto 3)

MVP profesional para gestionar múltiples cuentas sociales con autenticación segura, dashboard y base preparada para respuestas automáticas con IA.

## Stack
- **Frontend**: React + Vite + TypeScript + Nginx (imagen ligera)
- **Backend**: FastAPI + SQLAlchemy + JWT + passlib/bcrypt
- **DB**: PostgreSQL (alpine)
- **Cache/colas**: Redis (alpine)
- **Orquestación**: Docker Compose

## Funcionalidades MVP
- Login/registro seguro con contraseñas hasheadas
- JWT access token con expiración
- Multi-cuenta por usuario (ownership checks)
- Guardado seguro de tokens sociales/OpenAI (encriptados con `APP_SECRET_KEY`)
- Dashboard API con:
  - últimas publicaciones
  - últimos reels
  - últimos comentarios
  - últimas respuestas
- Endpoint de sincronización real para Instagram Graph API (usa token + Instagram User ID)

## Seguridad
- Password hashing (`bcrypt`)
- JWT firmado (`HS256`)
- Encriptación de tokens API (`Fernet`)
- CORS configurable
- Separación por usuario en todas las consultas de cuentas

## Arranque rápido
```bash
docker compose up --build
```

Frontend: http://localhost:5173  
Backend docs: http://localhost:8000/docs

## Variables de entorno
Copia `.env.example` a `.env` y ajusta secretos.

## Roadmap inmediato
- Integración real con Meta Graph API (OAuth + webhooks)
- Worker asíncrono para polling cada 3 minutos
- Motor de filtrado/relevancia
- Motor de generación de respuestas IA con prompts por cuenta
