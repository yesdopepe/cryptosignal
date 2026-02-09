# Deployment Guide

## 1. Production Readiness Checklist

You are now set up for a production-ready deployment with Docker, Nginx, and PostgreSQL.

### Nginx (Reverse Proxy)
I have created the `nginx/nginx.conf` file for you. It is configured to:
- Serve on port 80.
- Proxy requests to the FastAPI backend.
- Include security headers.
- **Action Required**: For SSL/HTTPS, uncomment the SSL section in `nginx/nginx.conf` and place your certificates in `nginx/ssl/`.

### Database Migrations (Alembic)
I have set up **Alembic** for database migrations. This replaces the "create all tables on startup" approach with a professional migration workflow.

**To initialize the database:**
1. Make sure your database is running (e.g., via Docker).
2. Generate the first migration:
   ```bash
   cd apps/api
   alembic revision --autogenerate -m "Initial migration"
   ```
3. Apply the migration:
   ```bash
   alembic upgrade head
   ```

### Environment Variables
Ensure your `.env` file (or CI/CD secrets) has:
- `SECRET_KEY`: A long, random string.
- `DATABASE_URL`: The PostgreSQL connection string.
- `DEBUG=false`: For production.

## 2. Replacing Database with PostgreSQL

Your project is already configured to use PostgreSQL in production via `docker-compose.prod.yml`.

### Switching Local Development to PostgreSQL (Optional)
If you want to use Postgres locally instead of SQLite:
1. Update `.env`:
   ```properties
   DATABASE_URL=postgresql+asyncpg://crypto:password@localhost:5432/crypto_signals
   ```
2. Start the Postgres service:
   ```bash
   docker compose -f docker-compose.prod.yml up -d postgres
   ```

### Deploying to Production (with PostgreSQL)

To launch the full production stack (App + Postgres + Redis + Nginx):

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

This will:
1. Start PostgreSQL (v16).
2. Start Redis.
3. Build and start the FastAPI app (configured to talk to Postgres).
4. Start Nginx as the gateway.

### Data Persistence
- PostgreSQL data is persisted in the `postgres-data` volume.
- Redis data is persisted in the `redis-data` volume.
