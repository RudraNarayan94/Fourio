<!-- <h1 align="center">Fourio 🎵</h1> -->

<p align="center">
  <!-- <a href="https://drive.google.com/file/d/1t2RdF4a-nRbqmLAzZ4dTgXcXU4G1T3RZ/view?usp=drive_link" target="_blank"> -->
    <img src="static/banner.png"
         alt="Fourio Preview"
         width="830"
         height="300">
  </a>
</p>


<!-- <p align="center">
  <a href="YOUR_VIDEO_LINK_HERE" target="_blank">
    ▶ Watch Demo Video
  </a>
</p> -->


## Description

**Fourio** is a command-line implementation of a music recognition system inspired by **Shazam**.The name is a portmanteau of **"Fourier"** and **"Audio"** named after the [**Fourier Transform**](https://en.wikipedia.org/wiki/Fourier_transform).It analyzes song fingerprints, detects matches from local or downloaded tracks, and integrates with Spotify and YouTube for metadata and previews. It has addtional features like a REST APIs, Multiple DB support like MongoDB and SQLite.

This version of **Fourio** is fully written in **Python**, powered by:
- ⚡ **FastAPI** — backend API framework for high-performance web services  
- 🧠 **Typer** — command-line interface (CLI) for intuitive developer experience  
- 🧩 **uv** — ultra-fast dependency manager and environment tool  
- 🎵 **ffmpeg** — audio conversion and processing utility  
- ☁️ **Spotify API** — metadata integration for tracks, albums, and playlists
- 🎞️ **YouTube API** — for fetching song previews and additional metadata

## Project Struture
  ```bash
  fourio/
  ├── app/
  │   ├── api/                   # Web API endpoints
  │   ├── utils/                 # Logging, file handling, general utilities
  │   ├── db/                    # Database connection and operations
  │   ├── models/                # Data models
  │   ├── services/              # Different services like Spotify, YouTube and WAV conversion
  │   ├── core/                  # Core fingerprinting, Spectrogram and matching logic
  │   └── main.py                # FastAPI entry point
  ├── .env                       # Environment variables
  ├── Dockerfile                 # Docker image definition
  ├── docker-compose.yml         # Default Docker setup
  ├── docker-compose.mongo.yml   # MongoDB-only services
  ├── docker-compose.hybrid.yml  # Hybrid deployment setup
  ├── Makefile                   # Helper commands for Docker workflows
  ├── pyproject.toml             # uv dependencies
  ├── requirements.txt           # Python dependencies  (Optional)
  ├── cli_logic.py               # CLI logic        
  ├── cli.py                     # Typer CLI entry point
  ├── .gitignore
  ├── README.md
  └── LICENSE
  ```
---


## Installation

Choose one of the following setup methods:

### 🐳 Docker Setup (Recommended)
👉 [Complete Docker-based setup guide](./README_DOCKER.md)

---

### 🛠 Manual Setup
👉 [local Python environment setup](./README_MANUAL.md)



## 🧠 Usage
Run CLI
```bash
uv run python cli.py --help
```
![alt text](static/image.png)
## CLI-Commands
| Command                           | Description                                               |
| --------------------------------- | --------------------------------------------------------- |
| `find <path_to_audio_file>`       | Analyze audio file in any format and find matching fingerprints         |
| `download <spotify_url>`          | Download and process a song/album/playlist from Spotify   |
| `save <path_or_dir> [--force/-f]` | Fingerprint and save local songs                          |
| `erase`                           | Clear all stored songs and fingerprints from the database |
<!-- | `serve --proto http --port 8000`  | Start the FastAPI backend server                          | -->
# 🌐 API Access & Documentation

When the backend server or Docker environment is running:

| Interface | URL | Description |
|-----------|-----|-------------|
| **Backend Service** | [http://localhost:8000](http://localhost:8000) | Root status check |
| **Swagger UI Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive API exploration and testing |
| **ReDoc** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Alternative OpenAPI documentation |

## 📡 Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/fourio/match` | POST | Match audio fingerprint against database and return top 10 matches |
| `/recordings/save` | POST | Save base64-encoded audio recording as WAV file |
| `/songs/total` | GET | Get total number of indexed songs in database |
| `/songs/download` | POST | Download and process Spotify/YouTube track, album, or playlist |
| `/songs` | DELETE | Delete song from database by ID, YouTube ID, or title + artist |

### 💡 Examples
#### 📌Run Server
```bash
uv run python -m uvicorn app.main:app --reload
```
#### ▶ Download a Spotify track
```bash
uv run python cli.py download https://open.spotify.com/track/4pqwGuGu34g8KtfN8LDGZm
```

#### 🔎 Find a song match
```bash
uv run python cli.py find songs/Voila.mp3
```

#### 💾 Save local songs
```bash
uv run python cli.py save ./local_songs/ --force
```

#### 🧹 Erase all data
```bash
uv run python cli.py erase
```

<!-- #### 🚀 Serve backend
```bash
uv run python cli.py serve --proto http --port 8000
``` -->



## 📚 Resources 
- [SeekTune - Go implementation of Shazam](https://github.com/cgzirim/seek-tune.git)(main resource)
- [How does Shazam work - Coding Geek](https://drive.google.com/file/d/1ahyCTXBAZiuni6RTzHzLoOwwfTRFaU-C/view) (main resource)
- [Song recognition using audio fingerprinting](https://hajim.rochester.edu/ece/sites/zduan/teaching/ece472/projects/2019/AudioFingerprinting.pdf)
- [How does Shazam work - Toptal](https://www.toptal.com/algorithms/shazam-it-music-processing-fingerprinting-and-recognition)
- [Creating Shazam in Java](https://www.royvanrijn.com/blog/2010/06/creating-shazam-in-java/) 

---

## 🧑‍💻 Author

### Rudra Narayan Sahoo
 - Connect with me on [LinkedIn](https://www.linkedin.com/in/rudra404/).
 - Check out my other [GitHub](https://github.com/RudraNarayan94) projects.



## 🚀 Future Roadmap

Fourio have the potential to gradually evolve into a full-stack system with a modern UI and scalable backend. Feel free to contribute or suggest features!

### ⚙️ Backend (FastAPI)
- WEBSOCKETS Endpoints for song processing & matching 
<!-- - Redis for backend service  -->
<!-- - `/songs` → list stored entries   --> 
<!-- - Faster async matching & caching   -->


### 🧠 Fingerprinting Engine
<!-- - Cleaner service-layer architecture   -->
- Better DB Schema for fingerprints 
- Tunable fingerprint density & thresholds  

### ☁️ Deployment
<!-- - Docker setup   -->
- Optional FFmpeg/GPU acceleration  
<!-- - Remote MongoDB sync   -->

<!-- ### 🧩 Long-Term Ideas
- Browser “Music Finder” mode  
- User library for recordings   -->


---
## 📜 License

This project is licensed under the [**MIT License**](https://github.com/RudraNarayan94/Fourio/blob/main/LICENCE).