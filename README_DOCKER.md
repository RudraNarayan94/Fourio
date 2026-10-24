# 🐳 Docker Setup

This guide explains how to run **Fourio** using Docker and Docker Compose.

---

# ✔ Prerequisites

Install the following:

- Docker
- Docker Compose

Verify installation:

```bash
docker --version
docker compose version
```

---

# 📁 Docker Files

| File | Purpose |
|------|----------|
| `Dockerfile` | Docker image definition |
| `docker-compose.yml` | Default application setup |
| `docker-compose.mongo.yml` | MongoDB-only setup |
| `docker-compose.hybrid.yml` | Mongo + Redis environment setup |
| `Makefile` | Helper commands for Docker workflows |

---

# 🚀 Quick Start

## 1. Clone Repository

```bash
git clone https://github.com/RudraNarayan94/Fourio.git
cd fourio
```

---

## 2. Configure Environment Variables

Create a `.env` file in the project root.

Use `.env.example` as reference:

```bash
cp .env.example .env
```

Example `.env` configuration:

```env
# Database Mode: mongo, hybrid, or sqlite
DB_TYPE=hybrid
DB_USER=user
DB_PASS=password
DB_NAME=fourio
DB_HOST=mongo
DB_PORT=27017

# Direct Connection Strings (used by the app)
MONGO_URL=mongodb://user:password@mongo:27017/fourio
REDIS_URL=redis://redis:6379/0

# API Keys
SPOTIFY_CLIENT_ID=your-spotify-client-id
SPOTIFY_CLIENT_SECRET=your-spotify-client-secret
YOUTUBE_API_KEY=your-youtube-api-key
```

> **Note**: When running inside Docker via Compose, use container hostnames (`DB_HOST=mongo`, `REDIS_URL=redis://redis:6379/0`). When running locally outside Docker, use `localhost` (e.g. `127.0.0.1:27017` / `127.0.0.1:6379`).

---

# ⚡ Makefile Commands

The project includes helper Makefile commands for easier Docker management.

## ▶ Start Default Environment

```bash
make up
```

---

## 🧪 Run Mongo Environment

```bash
make up-mongo
```

---
## 🧪 Run Hybrid Environment (Mongo + Redis)

```bash
make up-hybrid
```

---

## 🛑 Stop Containers

```bash
make down
```

---

# 🐳 Manual Docker Commands

If you don't have `make` installed, you can run the Docker Compose commands directly:

### 1. Hybrid Environment (Mongo + Redis - Recommended)
```bash
docker compose -f docker-compose.yml -f docker-compose.hybrid.yml up --build
```
Detached mode:
```bash
docker compose -f docker-compose.yml -f docker-compose.hybrid.yml up -d --build
```

### 2. MongoDB-Only Environment
```bash
docker compose -f docker-compose.yml -f docker-compose.mongo.yml up --build
```

### 3. Default (API Only)
```bash
docker compose up --build
```

---

## Stop Containers

```bash
docker compose -f docker-compose.yml -f docker-compose.hybrid.yml down
```

---

## View Logs

```bash
docker compose logs -f
```

---

# 🔌 API Access

Once running:

| Service | URL |
|---------|-----|
| FastAPI | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |

---

# 🧹 Cleanup

Remove containers, networks, and volumes:

```bash
docker compose down -v
```

---

# 📚 Notes

- Docker setup includes all required runtime dependencies.
- FFmpeg is already installed inside the container.
- Recommended for development and deployment.