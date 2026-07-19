import os
import time
import subprocess
import concurrent.futures 
from typing import List, Tuple, Optional
from pathlib import Path

from app.db.db_clients import get_db_client
from app.models.model import Track
from app.services.spotify.spotify_service import TrackInfo, PlaylistInfo, AlbumInfo 
from app.services.spotify.youtube_service import GetYoutubeId  
from app.utils.utils import GenerateSongKey
from app.utils.logger_setup import GetLogger
from app.services.spotify.utils import SongKeyExists, YtIDExists, correctFilename, GetFileSize
from app.utils.file_io import DeleteFile
from app.services.wav.wav_converter import ConvertToWAV
from app.services.wav.wav_io import ReadWavInfo, WavBytesToSamples
from app.core.spectrogram import Spectrogram, ExtractPeaks
from app.core.fingerprint import Fingerprint

DELETE_SONG_FILE = False 
NUM_CPUS = os.cpu_count() or 1 

logger = GetLogger()


def get_yt_id(track_copy: Track) -> Tuple[Optional[str], Optional[Exception]]:
    """handles ID existence check and retry"""
    
    # 1: Initial attempt to get YT ID
    yt_id, err = GetYoutubeId(track_copy)
    if err:
        return None, err
    if not yt_id:
        return None, Exception("YouTube ID not found after search.")

    # 2: Check if YouTube ID already exists in DB
    ytid_exists, err = YtIDExists(yt_id)
    if err:
        return None, Exception(f"error checking YT ID existence: {err}")

    if ytid_exists:
        logger.warning(f"YouTube ID ({yt_id}) exists. Trying second search...")

        # Retry: Get YouTube ID again
        yt_id, err = GetYoutubeId(track_copy)
        if err or not yt_id:
            return None, err
        
        # 3: Check if the new YouTube ID also exists
        ytid_exists, err = YtIDExists(yt_id)
        if err:
            return None, Exception(f"error checking YT ID existence (retry): {err}")

        if ytid_exists:
            return None, Exception(f"YouTube ID ({yt_id}) exists after retry.")
    
    return yt_id, None


def download_yt_audio(id: str, path: str, file_path: str) -> Optional[Exception]:
    """
    NOTE: here yt-dlp used as the standard tools. youtube-dl, pytube are deprecated.
    """
    
    # 1. Path Validation
    if not os.path.isdir(path):
        return Exception("The path is not valid (not a directory)")
    
    # 2. Build yt-dlp/ffmpeg command for audio download (itag 140 = m4a, 128k)
    # yt-dlp uses the 'best audio' format, often m4a (itag 140)
    # The output path template is used to ensure the file is named correctly.
    cmd = [
        "yt-dlp",
        "--extract-audio",              # Extract audio only
        "--audio-format", "m4a",        # Specify format (m4a)
        "--audio-quality", "128K",      # Equivalent to Itag 140 quality
        "--extractor-args", "youtube:player_client=web_mobile",  # Use web_mobile to avoid SABR
        "--no-warnings",                # Suppress warnings
        "-o", file_path,                # Output template (e.g., /path/to/Track - Artist.m4a)
        f"https://www.youtube.com/watch?v={id}",
    ]
    
    # loops until fileSize > 0 (addressing intermittent download failures)
    file_size = 0
    max_attempts = 3
    
    for attempt in range(max_attempts):
        try:
            subprocess.run(cmd, check = True, capture_output = True)
            file_size, _ = GetFileSize(file_path) 
            
            if file_size > 0:
                return None # Success
            
            logger.warning(f"Download attempt {attempt + 1} failed. Retrying...")
            time.sleep(1) # Wait before retrying
            
        except subprocess.CalledProcessError as e:
            return Exception(f"yt-dlp failed: {e.stderr.decode()}")
        except Exception as e:
            return Exception(f"Error during YouTube download: {e}")
            
    return Exception("Failed to download audio stream after multiple retries.")


def add_tags(file_path: str, track: Track) -> Optional[Exception]:
    """Uses FFmpeg to write metadata."""
    
    # 1. Define temporary file path (Appending "2" before extension)
    path_obj = Path(file_path)
    temp_file = path_obj.parent / f"{path_obj.stem}2{path_obj.suffix}"
    
    # 2. Execute FFmpeg command to add tags
    cmd = [
        "ffmpeg", 
        "-y",
        "-i", file_path,
        "-c", "copy",
        "-metadata", f"album_artist={track.Artist}",
        "-metadata", f"title={track.Title}",
        "-metadata", f"artist={track.Artist}",
        "-metadata", f"album={track.Album}",
        str(temp_file),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True) 
        # 3. Rename temporary file to the original filename
        os.replace(str(temp_file), file_path)
        return None
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to add tags: {e.stderr.decode()}", output=e.stderr.decode())
        return Exception(f"Failed to add tags: {e.stderr.decode()}")
    except Exception as e:
        logger.error(f"Failed to rename file: {e}")
        return Exception(f"Failed to rename file: {e}")


def ProcessAndSaveSong(song_file_path: str, song_title: str, song_artist: str, yt_id: str) -> Optional[Exception]:
    """End-to-end processing pipeline (DSP, DB registration, Fingerprinting)"""
    
    db_client = get_db_client()
    
    with db_client: 
        # 1. Convert downloaded audio to standardized WAV (forces 44100Hz, 16-bit, Mono)
        # print("Entering ConvertToWAV")
        wav_file_path, err = ConvertToWAV(song_file_path, 1)
        if err:
            logger.error(f"Failed to convert to WAV: {err}")
            return err

        # 2. Read WAV info and extract float samples
        # print("Entering ReadWavInfo")
        wav_info, err = ReadWavInfo(wav_file_path)
        if err:
            logger.error(f"Failed to read WAV info: {err}")
            return err
        
        # print("Entering WavBytesToSamples")
        samples, err = WavBytesToSamples(wav_info.Data)
        if err:
            logger.error(f"Error converting WAV bytes to samples: {err}")
            return err
        
        # print("Number of samples: ", len(samples))
        # 3. DSP Pipeline (Spectrogram, Peaks, Fingerprints)
        # print("Entering Spectrogram")
        spectro, err = Spectrogram(samples, wav_info.SampleRate)
        if err:
            logger.error(f"Error creating spectrogram: {err}")
            return err
        
        # 4. DB Registration
        # print("Entering RegisterSong")
        song_id, err = db_client.RegisterSong(song_title, song_artist, yt_id)
        if err:
            logger.error(f"Failed to register song: {err}")
            return err

        # print("Entering ExtractPeaks & Fingerprint")
        peaks = ExtractPeaks(spectro, wav_info.Duration)
        fingerprints = Fingerprint(peaks, song_id)

        # 5. Store Fingerprints
        # print(f"Storing fingerprints for {song_title} by {song_artist}...")
        err = db_client.StoreFingerprints(fingerprints)
        if err:
            # Delete song if fingerprint storage fails
            # print("Storing fingerprints for {song_title} by {song_artist} ")
            db_client.DeleteSongByID(song_id)
            logger.error(f"Failed to store fingerprints: {err}")
            return Exception(f"error storing fingerprint: {err}")
        
        logger.info(f"Fingerprint for {song_title} by {song_artist} saved in DB successfully")
        return None

# --- Main DL Functions ---

def dl_track_concurrent(tracks: List[Track], path: str) -> Tuple[int, Optional[Exception]]:
    """concurrent downloading of tracks"""
    
    download_count = 0
    # Use ThreadPoolExecutor for semaphore concurrency management
    with concurrent.futures.ProcessPoolExecutor(max_workers = NUM_CPUS) as executor:
        futures = []
        
        for t in tracks:
            # Submit each download task to the thread pool
            future = executor.submit(process_single_track_task, t, path)
            futures.append(future)

        # Iterate over results as they complete
        for future in concurrent.futures.as_completed(futures):
            result_err = future.result()
            if result_err is None:
                download_count += 1
            else:
                logger.error(f"Track processing failed: {result_err}")
                
    logger.info(f"Total tracks downloaded: {download_count}")
    return download_count, None

def process_single_track_task(track: Track, path: str) -> Optional[Exception]:
    """Helper function to execute the logic for a single track within a thread."""
    
    # 1. Check if song already exists
    key_exists, err = SongKeyExists(GenerateSongKey(track.Title, track.Artist))
    if err:
        logger.error(f"Error checking song existence for '{track.Title}': {err}")
        return err # Return error to be logged by the executor
    if key_exists:
        logger.info(f"'{track.Title}' by '{track.Artist}' already exists.")
        return None # Success (skip)

    # 2. Get YouTube ID (with existence check)
    yt_id, err = get_yt_id(track)
    if err:
        logger.error(f"'{track.Title}' by '{track.Artist}' could not be downloaded: {err}")
        return err
    
    # 3. Prepare File Paths (and correct filename)
    track_title, track_artist = correctFilename(track.Title, track.Artist)
    file_name = f"{track_title} - {track_artist}"
    # Start with m4a download path
    file_path = Path(path) / f"{file_name}.m4a"

    # 4. Download Audio
    err = download_yt_audio(yt_id, path, file_path)
    if err:
        logger.error(f"'{track_title}' by '{track_artist}' could not be downloaded: {err}")
        return err

    # 5. Process (WAV conversion, DSP, DB registration)
    err = ProcessAndSaveSong(file_path, track_title, track_artist, yt_id)
    if err:
        logger.error(f"Failed to process song ('{track_title}' by '{track_artist}'): {err}")
        # Clean up the downloaded m4a if processing fails
        DeleteFile(file_path)
        return err
        
    # 6. Clean up temporary m4a file
    DeleteFile(file_path) 

    # 7. Add Metadata Tags (Assumes tags are applied to the processed WAV file)
    wav_file_path = Path(path) / f"{file_name}.wav"
    err = add_tags(wav_file_path, track)
    if err:
        logger.error(f"Error adding tags to {wav_file_path}: {err}")
        return err
    
    # 8. Final Cleanup (if DELETE_SONG_FILE is true)
    if DELETE_SONG_FILE:
        DeleteFile(wav_file_path)

    logger.info(f"'{track.Title}' by '{track.Artist}' was downloaded and registered.")
    return None 


# --- API Functions ---

def DlSingleTrack(url: str, save_path: str) -> Tuple[int, Optional[Exception]]:
    logger.info(f"Getting track info for url: {url}")
    track_info, err = TrackInfo(url)
    if err: 
        return 0, err
    
    logger.info("Now downloading track")
    return dl_track_concurrent([track_info], save_path)


def DlPlaylist(url: str, save_path: str) -> Tuple[int, Optional[Exception]]:
    tracks, err = PlaylistInfo(url)
    if err: 
        return 0, err

    time.sleep(1)
    logger.info("Now downloading playlist")
    return dl_track_concurrent(tracks, save_path)


def DlAlbum(url: str, save_path: str) -> Tuple[int, Optional[Exception]]:
    tracks, err = AlbumInfo(url)
    if err: 
        return 0, err

    time.sleep(1)
    logger.info("Now downloading album")
    return dl_track_concurrent(tracks, save_path)