import json
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from app.db.db_clients import get_db_client
from app.models.model import DBClient
from app.services.spotify.spotify_service import TrackInfo, PlaylistInfo, AlbumInfo 
from app.utils.utils import GenerateSongKey
from app.utils.logger_setup import GetLogger
from app.services.spotify.download_manager import DlAlbum, DlPlaylist, DlSingleTrack, ProcessAndSaveSong

router = APIRouter(prefix="/songs", tags=["songs"])
logger = GetLogger()
SONGS_DIR = "songs"

def extract_youtube_id(youtube_url: str) -> str:
    """Extract YouTube video ID from various YouTube URL formats."""
    # Pattern for youtube.com/watch?v=VIDEO_ID
    match = re.search(r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]+)', youtube_url)
    if match:
        return match.group(1)
    return "" 



def download_status(status_type: str, message: str) -> str:
    data = {"type": status_type, "message": message}
    return json.dumps(data)

# --------------------------------------------------------------------
# 1. GET /songs/total
# --------------------------------------------------------------------
@router.get("/total", response_model=Dict[str, int])
def handle_total_songs(db: DBClient = Depends(get_db_client)):
    """Returns the total number of indexed songs in the database."""
    try:
        total_songs, err = db.TotalSongs()
        if err:
            logger.error(f"Error getting total songs: {err}")
            raise HTTPException(status_code=500, detail="Failed to retrieve song count")
            
        return {"totalSongs": total_songs}
    finally:
        pass

# --------------------------------------------------------------------
# 2. POST /songs/download
# --------------------------------------------------------------------
@router.post("/download", response_model=Dict[str, Any])
async def handle_song_download(url: str, db: DBClient = Depends(get_db_client)):
    """
    Downloads and processes songs from Spotify or YouTube URLs.
    Supports: Spotify (track/album/playlist) or YouTube video URLs.
    """
    # Helper function to manage download results
    def _handle_download_result(dl_func, download_url, type_name):
        total_downloaded, err = dl_func(download_url, SONGS_DIR)
        if err:
            logger.error(f"Failed to download {type_name} {download_url}: {err}")
            short_err = str(err)[:50] if len(str(err)) > 50 else str(err)
            return download_status("error", f"Couldn't download {type_name}. Error: {short_err}")
        status_msg = f"{total_downloaded} songs downloaded from {type_name}."
        return download_status("success", status_msg)

    # Helper to download from YouTube
    def _download_from_youtube(youtube_url: str):
        try:
            logger.info(f"Downloading from YouTube: {youtube_url}")
            
            # Extract YouTube ID early
            youtube_id = extract_youtube_id(youtube_url)
            if not youtube_id:
                return None, "Could not extract YouTube video ID from URL"
            
            # Download audio using yt-dlp
            output_path = os.path.join(SONGS_DIR, "%(title)s.%(ext)s")
            cmd = [
                "yt-dlp",
                "-f", "bestaudio/best",
                "-x",
                "--audio-format", "mp3",
                "--extractor-args", "youtube:player_client=web_mobile",  # Use web_mobile to avoid SABR
                "--no-warnings",  # Suppress warnings
                "-o", output_path,
                youtube_url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                return None, f"YouTube download failed: {result.stderr}"
            
            # Find the most recently created file
            song_files = sorted([f for f in os.listdir(SONGS_DIR) if f.endswith(('.mp3', '.m4a', '.wav'))],
                              key=lambda f: os.path.getctime(os.path.join(SONGS_DIR, f)), reverse=True)
            
            if not song_files:
                return None, "Could not determine downloaded file path"
            
            downloaded_file = os.path.join(SONGS_DIR, song_files[0])
            logger.info(f"Downloaded: {downloaded_file}")
            
            # Extract title and artist from filename
            filename = Path(downloaded_file).stem
            title = filename
            artist = "YouTube"
            
            if " - " in filename:
                parts = filename.split(" - ", 1)
                artist = parts[0].strip()
                title = parts[1].strip()
            
            logger.info(f"Processing: {title} by {artist} (YouTube ID: {youtube_id})")
            
            # Process and save with YouTube ID
            err = ProcessAndSaveSong(downloaded_file, title, artist, youtube_id)
            if err:
                return None, f"Failed to process song: {err}"
            
            return (title, artist, youtube_id), None
            
        except subprocess.TimeoutExpired:
            return None, "Download timeout (exceeded 5 minutes)"
        except Exception as e:
            logger.error(f"YouTube download error: {e}", exc_info=True)
            return None, str(e)

    # Check URL type and process accordingly
    if "youtube.com" in url or "youtu.be" in url:
        # YouTube URL
        song_info, err = _download_from_youtube(url)
        if err:
            return {"status": download_status("error", f"YouTube download failed: {err}")}
        
        title, artist, youtube_id = song_info
        return {"status": download_status("success", f"'{title}' by '{artist}' was downloaded from YouTube")}

    elif "spotify.com" in url:
        # Spotify URL handling (original logic)
        if "album" in url:
            tracks_in_album, err = AlbumInfo(url)
            if err:
                raise HTTPException(500, detail=f"Error getting album info: {str(err)[:50]}")
            logger.info(f"{len(tracks_in_album)} songs found in album.")
            status_json = _handle_download_result(DlAlbum, url, "album")
            return {"status": status_json}

        elif "playlist" in url:
            tracks_in_pl, err = PlaylistInfo(url)
            if err:
                raise HTTPException(500, detail=f"Error getting playlist info: {str(err)[:50]}")
            logger.info(f"{len(tracks_in_pl)} songs found in playlist.")
            status_json = _handle_download_result(DlPlaylist, url, "playlist")
            return {"status": status_json}

        elif "track" in url:
            track_info, err = TrackInfo(url)
            if err:
                raise HTTPException(500, detail=f"Error getting track info: {str(err)[:50]}")
            
            song_key = GenerateSongKey(track_info.Title, track_info.Artist)
            _, song_exists, err = db.GetSongByKey(song_key)
            
            if song_exists:
                song, _, _ = db.GetSongByKey(song_key)
                msg = f"'{song.Title}' by '{song.Artist}' already exists (https://www.youtube.com/watch?v={song.YouTubeID})"
                return {"status": download_status("error", msg)}
            
            total_downloads, err = DlSingleTrack(url, SONGS_DIR)
            if err:
                return {"status": download_status("error", str(err))}
            
            if total_downloads == 1:
                msg = f"'{track_info.Title}' by '{track_info.Artist}' was downloaded"
                return {"status": download_status("success", msg)}
            else:
                msg = f"'{track_info.Title}' by '{track_info.Artist}' failed to download"
                return {"status": download_status("error", msg)}

    raise HTTPException(status_code=400, detail="URL must be a valid Spotify or YouTube link.")