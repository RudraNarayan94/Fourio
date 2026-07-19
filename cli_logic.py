import os
import sys
import math
import time
import subprocess
from typing import  Optional
from pathlib import Path
import re

# project imports
from app.services.wav.wav_io import ReadWavInfo, WavBytesToSamples, GetMetadata
from app.services.wav.wav_converter import ConvertToWAV
from app.core.shazam import FindMatches
from app.services.spotify.youtube_service import GetYoutubeId
from app.services.spotify.download_manager import ProcessAndSaveSong, DlSingleTrack, DlPlaylist, DlAlbum
from app.utils.logger_setup import GetLogger
from app.db.db_clients import NewDBClient
from app.utils.file_io import CreateFolder, MoveFile, DeleteFile
from app.models.model import Track
logger = GetLogger()
SONGS_DIR = "songs"
YELLOW_COLOR_CODE = "\033[93m" #yellow text
RESET_COLOR_CODE = "\033[0m"

def yellow_print(message: str):
    print(f"{YELLOW_COLOR_CODE}{message}{RESET_COLOR_CODE}", file=sys.stderr)

def extract_youtube_id(youtube_url: str) -> str:
    """Extract YouTube video ID from various YouTube URL formats."""
    # Pattern for youtube.com/watch?v=VIDEO_ID or youtu.be/VIDEO_ID
    match = re.search(r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]+)', youtube_url)
    if match:
        return match.group(1)
    return ""

# ----------------------------------------------------------------------
# --- CLI Command Implementations ---
# ----------------------------------------------------------------------

def find(file_path: str):
    input_path = Path(file_path)
    
    if not input_path.exists():
        yellow_print(f"Error: File does not exist: {file_path}")
        return
    
    # checking if needs conversion
    original_file = file_path
    is_wav = input_path.suffix.lower() == '.wav'
    needs_cleanup = False
    wav_file_path = file_path
    if not is_wav:
        print(f"Converting {input_path.suffix} to WAV format...")
        wav_file_path, err = ConvertToWAV(file_path, channels=1)
        if err:
            yellow_print(f"Error converting file to WAV: {err}")
            return
        needs_cleanup = True 
        print(f"Conversion complete: {wav_file_path}")

    try:
        # 1. Read WAV Info and Samples
        wav_info, err = ReadWavInfo(wav_file_path)
        if err:
            yellow_print(f"Error reading wave info: {err}")
            return
            
        samples, err = WavBytesToSamples(wav_info.Data)
        if err:
            yellow_print(f"Error converting to samples: {err}")
            return

        # 2. Find Matches
        start_time = time.time()
        matches, _, err = FindMatches(samples, wav_info.Duration, wav_info.SampleRate)
        search_duration = time.time() - start_time
        
        if err:
            yellow_print(f"Error finding matches: {err}")
            return

        # 3. Output Results 
        duration_str = f"{search_duration:.4f}s" 

        if not matches:
            print("\nNo match found.")
            print(f"\nSearch took: {duration_str}")
            return

        top_matches = matches[:20]
        msg = "Top 20 matches:" if len(matches) >= 20 else "Matches:"

        print(f"\n{msg}")
        for match in top_matches:
            print(f"\t- {match.SongTitle} by {match.SongArtist}, score: {match.Score:.2f}")
        print(f"\nSearch took: {duration_str}")
    
        # Final Prediction
        top_match = top_matches[0]
        print(f"\nFinal prediction: {top_match.SongTitle} by {top_match.SongArtist} , score: {top_match.Score:.2f}")
    finally:
        if needs_cleanup and wav_file_path != original_file:
            print(f"\nCleaning up temporary file: {wav_file_path}")
            err = DeleteFile(wav_file_path)
            if err:
                yellow_print(f"Warning: Failed to delete temporary file: {err}")


def download(url: str):
    err = CreateFolder(SONGS_DIR)
    if err:
        logger.error(f"Failed to create directory {SONGS_DIR}: {err}")
        return
    
    # Check if it's a YouTube URL
    if "youtube.com" in url or "youtu.be" in url:
        download_from_youtube(url)
    # Check if it's a Spotify URL
    elif "spotify.com" in url:
        # Dispatch download based on URL content
        if "album" in url:
            total_downloaded, download_error = DlAlbum(url, SONGS_DIR)
        elif "playlist" in url:
            total_downloaded, download_error = DlPlaylist(url, SONGS_DIR)
        elif "track" in url:
            total_downloaded, download_error = DlSingleTrack(url, SONGS_DIR)
        else:
            download_error = Exception(f"Invalid Spotify URL type: {url}")

        if download_error:
            yellow_print(f"Error: {download_error}")
        else:
            print(f"\nDownload process initiated successfully for {url}.")
    else:
        yellow_print(f"Error: URL must be a Spotify or YouTube URL")


def download_from_youtube(youtube_url: str):
    """Download a song from YouTube URL and fingerprint it."""
    try:
        print(f"Downloading from YouTube: {youtube_url}")
        
        # Extract YouTube ID early
        youtube_id = extract_youtube_id(youtube_url)
        if not youtube_id:
            yellow_print("Error: Could not extract YouTube video ID from URL")
            return
        
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
            yellow_print(f"Error downloading from YouTube: {result.stderr}")
            return
        
        # Extract video title from yt-dlp output to get the downloaded file
        # yt-dlp outputs the filename in stdout
        output_lines = result.stdout.strip().split('\n')
        downloaded_file = None
        
        for line in output_lines:
            if "Destination:" in line:
                downloaded_file = line.split("Destination:")[-1].strip()
                break
        
        if not downloaded_file:
            # Try to find the most recently modified file in SONGS_DIR
            song_files = [f for f in os.listdir(SONGS_DIR) if f.endswith(('.mp3', '.m4a', '.wav'))]
            if song_files:
                downloaded_file = os.path.join(SONGS_DIR, max(song_files, key=lambda f: os.path.getctime(os.path.join(SONGS_DIR, f))))
        
        if not downloaded_file or not os.path.exists(downloaded_file):
            yellow_print("Error: Could not determine downloaded file path")
            return
        
        print(f"Downloaded: {downloaded_file}")
        
        # Extract title and artist from filename
        filename = Path(downloaded_file).stem
        # Try to parse "Artist - Title" format
        title = filename
        artist = "Unknown Artist"
        
        if " - " in filename:
            parts = filename.split(" - ", 1)
            artist = parts[0].strip()
            title = parts[1].strip()
        
        print(f"Processing: {title} by {artist} (YouTube ID: {youtube_id})")
        
        # Process and save the song with YouTube ID
        err = ProcessAndSaveSong(downloaded_file, title, artist, youtube_id)
        if err:
            yellow_print(f"Error processing song: {err}")
            return
        
        print(f"✓ Successfully saved: {title} by {artist}")
        
    except subprocess.TimeoutExpired:
        yellow_print("Error: Download timeout (exceeded 5 minutes)")
    except Exception as e:
        yellow_print(f"Error: {e}")
        logger.error(f"YouTube download error: {e}", exc_info=True)


def erase(songs_dir: str):    
    # 1. Wipe DB collections
    db_client, err = NewDBClient()
    if err:
        logger.error(f"Error creating DB client: {err}")
        return
        
    with db_client: 
        # Note: DB clients having 'fingerprints' and 'songs' collections/tables
        err = db_client.DeleteCollection("fingerprints")
        if err:
            logger.error(f"Error deleting fingerprints collection: {err}")
        
        if err := db_client.DeleteCollection("songs"):
            logger.error(f"Error deleting songs collection: {err}")

    # 2. Delete song files (Walk directory and remove .wav and .m4a files)
    def remove_files_in_dir(directory):
        for root, _, files in os.walk(directory, topdown=False):
            for name in files:
                file_path = os.path.join(root, name)
                if file_path.endswith((".wav", ".m4a")):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        logger.error(f"Failed to remove file {file_path}: {e}")
                        
    try:
        remove_files_in_dir(songs_dir)
    except Exception as e:
        logger.error(f"Error walking through directory {songs_dir}: {e}")

    print("Erase complete")


# def serve(protocol: str, port: str):
#     """Corresponds to the Go serve(protocol, port) function (uses Uvicorn)."""
    
#     # In the Python/FastAPI environment, this function calls uvicorn.run(). 
#     # Since the serve logic is complex (HTTP, HTTPS, Socket.io), 
#     # the cli.py implementation of serve is the most direct translation.
    
#     # NOTE: The Go implementation includes complex socket.io setup and custom HTTP/HTTPS
#     # handlers. In Python, we delegate to Uvicorn and assume the FastAPI app (app.main:app)
#     # handles the HTTP logic.

#     # Re-running the uvicorn logic from cli.py for completeness:
#     try:
#         import uvicorn
        
#         app_string = "app.main:app"
#         port_int = int(port)
        
#         if protocol == "https":
#             # Go handles HTTPS with environment variables (CERT_KEY, CERT_FILE)
#             cert_key = GetEnv("CERT_KEY", "/etc/letsencrypt/live/localport.online/privkey.pem")
#             cert_file = GetEnv("CERT_FILE", "/etc/letsencrypt/live/localport.online/fullchain.pem")
            
#             if not cert_key or not cert_file:
#                  log.fatal("Missing CERT_KEY or CERT_FILE environment variables for HTTPS.")
            
#             log.info(f"Starting HTTPS server on 0.0.0.0:{port}")
#             uvicorn.run(
#                 app_string, 
#                 host="0.0.0.0", 
#                 port=port_int, 
#                 log_level="info", 
#                 ssl_keyfile=cert_key,
#                 ssl_certfile=cert_file
#             )

#         else: # HTTP case
#             log.info(f"Starting HTTP server on 0.0.0.0:{port}")
#             uvicorn.run(
#                 app_string, 
#                 host="0.0.0.0", 
#                 port=port_int, 
#                 log_level="info", 
#                 reload=True # For development ease
#             )
            
#     except Exception as e:
#         log.fatal(f"Server failed to start: {e}")


def save(path: str, force: bool):    
    # process a single file
    def save_song(file_path: str, force: bool) -> Optional[Exception]:
        # 1. Get metadata using ffprobe
        metadata, err = GetMetadata(file_path)
        if err: return err

        #duration (float) from metadata
        try:
            duration_str = metadata.get("format", {}).get("duration", "0.0")
            duration_float = float(duration_str)
        except ValueError:
            return Exception("Failed to parse duration.")

        #tags
        tags = metadata.get("format", {}).get("tags", {})
        
        track = Track(
            Album=tags.get("album", ""),
            Artist=tags.get("artist", ""),
            Title=tags.get("title", ""),
            Duration=int(math.ceil(duration_float)), 
            Artists=[], 
        )

        # 2. Get YouTube ID
        yt_id, err = GetYoutubeId(track)
        if err is not None and not force:
            return Exception(f"Failed to get YouTube ID for song: {err}")
        
        # 3. Final checks and prep
        if track.Title == "":
            track = track._replace(Title=Path(file_path).stem) # Use filename stem
        if track.Artist == "":
            return Exception("No artist found in metadata or filename.")

        # 4. Process (DSP/Fingerprint/DB Registration)
        # Note: ProcessAndSaveSong will automatically call ConvertToWAV internally if needed
        err = ProcessAndSaveSong(file_path, track.Title, track.Artist, yt_id or "")
        if err is not None:
            return Exception(f"Failed to process or save song: {err}")

        # 5. Move song file 
        file_name = Path(file_path).stem + ".wav"
        source_path = file_path # Assuming ProcessAndSaveSong leaves the WAV where it is
        new_file_path = os.path.join(SONGS_DIR, file_name)
        
        # NOTE: The MoveFile logic is tricky. It seems to assume the WAV file 
        # is created next to the source file. Assuming processed WAV is at source_path:
        
        # shutil.move is the Python equivalent of os.Rename (Go's MoveFile)
        try:
            MoveFile(source_path, new_file_path)
        except Exception as e:
            return Exception(f"Failed to move file from {source_path} to {new_file_path}: {e}")

        return None
    
    # --- Main save logic ---
    path_obj = Path(path)
    if path_obj.is_dir():
        for item in os.listdir(path):
            full_path = os.path.join(path, item)
            if os.path.isfile(full_path) and full_path.endswith((".wav", ".m4a", ".mp3")):
                err = save_song(full_path, force)
                if err:
                    print(f"Error saving song ({full_path}): {err}")
    elif path_obj.is_file():
        err = save_song(path, force)
        if err:
            print(f"Error saving song ({path}): {err}")
    else:
        print(f"Error: Path must be a valid file or directory: {path}")
