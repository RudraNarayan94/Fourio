import sys
import typer
from dotenv import load_dotenv 

import cli_logic 

from app.utils.logger_setup import GetLogger
from app.utils.file_io import CreateFolder 

# --- Configuration ---
app = typer.Typer(
  name="Fourio",
  help="Audio fingerprinting CLI.", 
)
logger = GetLogger()
SONGS_DIR = "songs" 
TMP_DIR = "tmp"

def main():    
    load_dotenv() 
        
    err = CreateFolder(TMP_DIR)
    if err:
        logger.error(f"Failed to create directory {TMP_DIR}: {err}")
        sys.exit(1)
        
    err = CreateFolder(SONGS_DIR)
    if err:
        logger.error(f"Failed to create directory {SONGS_DIR}: {err}")
        sys.exit(1)

    app()


# ----------------------------------------------------------------------
# --- CLI Subcommand Definitions (@app.command) ---
# ----------------------------------------------------------------------

@app.command(name="find", help="Analyzes any audio file and searches for matching songs in the database.")
def find_command(file_path: str = typer.Argument(..., help="Path to the audio file to analyze (e.g., audio.wav, audio.mp3, audio.m4a).")):
    
  cli_logic.find(file_path)


@app.command(name="download", help="Downloads and fingerprints a resource from Spotify or YouTube URL.")
def download_command(url: str = typer.Argument(..., help="Spotify or YouTube URL (track, playlist, album, or video link).")):
    
  cli_logic.download(url)


@app.command(name="erase", help="Deletes all indexed songs and fingerprints from the database.")
def erase_command():
    
  cli_logic.erase(SONGS_DIR)


@app.command(name="save", help="Saves (fingerprints) a local WAV file or directory of files to the database.")
def save_command(
    file_path: str = typer.Argument(..., help="Path to the WAV file or directory containing files to index."),
    
    force: bool = typer.Option(
        False, 
        "-f", 
        "--force", 
        help="Force saving even if the required metadata (like YouTube ID) is missing."
    )
):
    
  cli_logic.save(file_path, force)


if __name__ == "__main__":
  main()