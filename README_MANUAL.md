# 🛠 Fourio Manual Setup

This guide explains how to run **Fourio** locally without Docker.

---

# ✔ Prerequisites

## 🔹 Python 3.12+

Download:

https://www.python.org/downloads/

---

## 🔹 FFmpeg

Required for audio decoding and processing.

### Windows (Chocolatey)

```bash
choco install ffmpeg
```

Chocolatey install guide:
https://chocolatey.org/install

---

### macOS (Homebrew)

```bash
brew install ffmpeg
```

---

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install ffmpeg
```

---

Verify installation:

```bash
ffmpeg -version
```

---

## 🔹 uv Package Manager

Install guide:

https://github.com/astral-sh/uv

---

# 🚀 Setup Using uv (Recommended)

## 1. Clone Repository

```bash
git clone https://github.com/RudraNarayan94/Fourio.git
cd fourio
```



## 2. Create Virtual Environment

```bash
uv venv
```


## 3. Install Dependencies

```bash
uv sync
```



# 🐍 Alternative Setup Using venv + requirements.txt

## Create Virtual Environment

```bash
python -m venv venv
```

---

## Activate Environment

### macOS/Linux

```bash
source venv/bin/activate
```

### Windows

```bash
venv\Scripts\activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

# 🎵 Environment Configuration

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Use `.env.example` as reference:

```env
# Database Mode: mongo, hybrid, or sqlite
DB_TYPE=mongo
DB_USER=user
DB_PASS=password
DB_NAME=fourio
DB_HOST=localhost
DB_PORT=27017

MONGO_URL=mongodb://user:password@localhost:27017/fourio
REDIS_URL=redis://localhost:6379/0

SPOTIFY_CLIENT_ID=your-spotify-client-id
SPOTIFY_CLIENT_SECRET=your-spotify-client-secret
YOUTUBE_API_KEY=your-youtube-api-key
```

---

# ▶ Running the Application

## Run FastAPI Server

```bash
uv run python -m uvicorn app.main:app --reload
```

Once running, access the service:

| Service | URL | Description |
|---------|-----|-------------|
| **FastAPI Root** | [http://localhost:8000](http://localhost:8000) | Backend status |
| **Swagger UI** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive API exploration |
| **ReDoc** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | OpenAPI documentation |

---

# 🧠 CLI Commands

## Show CLI Help

```bash
uv run python cli.py --help
```

---

## Download Spotify Track

```bash
uv run python cli.py download https://open.spotify.com/track/4pqwGuGu34g8KtfN8LDGZm
```

---

## Find Song Match

```bash
uv run python cli.py find songs/Voila.mp3
```

---

## Save Local Songs

```bash
uv run python cli.py save ./local_songs/ --force
```

---

## Erase Database

```bash
uv run python cli.py erase
```

---

# 🔌 API Access

| Service | URL |
|---------|-----|
| FastAPI | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |

---

# 📚 Notes

- Manual setup is useful for local debugging and development.
- Ensure FFmpeg is available in system PATH.
- `uv` is the recommended dependency manager.