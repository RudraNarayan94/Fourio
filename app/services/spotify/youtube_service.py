import json
import requests
import urllib.parse
import subprocess
from typing import List, Tuple, Optional, Any, Dict
from dataclasses import dataclass, field 

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError as YouTubeAPIError

from app.models.model import Track 
from app.utils.logger_setup import GetLogger 
from app.utils.utils import GetEnv

logger = GetLogger()


@dataclass
class SearchResult:
    Title: str
    Uploader: str
    URL: str
    Duration: str     #(HH:MM:SS)
    ID: str
    Live: bool
    SourceName: str
    Extra: List[str] = field(default_factory=list) # additional info like views, likes, etc.


DEVELOPER_KEY = GetEnv("YOUTUBE_API_KEY", "") 
DURATION_MATCH_THRESHOLD = 5 # Seconds tolerance for matching duration
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
# SPOTIFY_API_BASE = "https://api.spotify.com/v1" 
HTTP_CLIENT = requests.Session()


def convert_string_duration_to_seconds(duration_str: str) -> int:
    """
    Converts a duration string in the format HH:MM:SS to seconds.
    """
    parts = list(map(int, duration_str.split(':')))[::-1]
    seconds = 0
    if len(parts) >= 1:
        seconds += parts[0]
    if len(parts) >= 2:
        seconds += parts[1] * 60
    if len(parts) >= 3:
        seconds += parts[2] * 3600
    return seconds

def extract_json_from_html(html: str) -> Optional[Dict[str, Any]]:
    """
    Safely extracts the main JSON payload (ytInitialData) from the YouTube HTML using 
    a balanced bracket parser for better resilience against structural changes.
    """
    start_token = 'var ytInitialData = '
    idx = html.find(start_token)
    if idx == -1:
        start_token = 'window["ytInitialData"] = '
        idx = html.find(start_token)
    if idx == -1:
        return None
    
    idx += len(start_token)
    brace_count, end_idx = 0, idx
    
    # find the matching closing brace '}'
    for i, c in enumerate(html[idx:], start=idx):
        if c == '{':
            brace_count += 1
        elif c == '}':
            brace_count -= 1
            if brace_count == 0:
                end_idx = i + 1
                break
    
    json_str = html[idx:end_idx].rstrip(';')
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode ytInitialData JSON: {e}")
        return None


def get_content(data: Dict[str, Any], index: int) -> Optional[List[Dict[str, Any]]]:
    """
    Path: contents -> twoColumnSearchResultsRenderer -> 
    primaryContents -> sectionListRenderer -> contents -> [index] -> 
    itemSectionRenderer -> contents
    """
    try:
        contents = data["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"]["sectionListRenderer"]["contents"]
        
        # Navigate to the correct section content based on the index
        item_section = contents[index]["itemSectionRenderer"]["contents"]
        return item_section
    except (KeyError, IndexError, TypeError):
        return None

def fallback_search_yt_dlp(track: Track) -> Optional[str]:
    """
    Implements the yt-dlp fallback search by executing a system command.
    Returns a single YouTube ID or None.
    """
    query = f"{track.Title} {track.Artist}".strip()
    if not query:
        return None
    cmd = ["yt-dlp", "--no-warnings", f"ytsearch1:{query}", "--get-id"]
    try:
        # Executes the command and captures output
        result = subprocess.check_output(cmd, text=True).strip()
        logger.info(f"Used yt-dlp fallback; ID found: {result}")
        return result or None
    except FileNotFoundError:
        logger.warning("yt-dlp not installed. Cannot use command fallback.")
        return None
    except Exception as e:
        logger.error(f"yt-dlp fallback search failed: {e}")
        return None


# --- YouTube API Search (Method 1: Official API) ---
def get_youtube_id_with_api(spTrack: Track) -> Tuple[Optional[str], Optional[Exception]]:
    if not DEVELOPER_KEY:
        return None, Exception("DEVELOPER_KEY is missing. Cannot use official YouTube API.")

    try:
        service = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=DEVELOPER_KEY)
        query = f"'{spTrack.Title}' {spTrack.Artist} {spTrack.Album}"
        request = service.search().list(q=query, part="id,snippet", videoCategoryId="10", type="video", maxResults=5)
        response = request.execute()
        
        for item in response.get("items", []):
            if item["id"]["kind"] == "youtube#video":
                return item["id"]["videoId"], None
                
        return None, Exception(f"YouTube API found no video ID for query: {query}")
        
    except YouTubeAPIError as e:
        logger.error(f"YouTube API call failed: {e}")
        return None, Exception(f"YouTube API call failed: {e}")
    except Exception as e:
        return None, Exception(f"Error creating new YouTube client: {e}")

# --- YouTube Scraper Search (Method 2: Custom Search) ---
def yt_search(search_term: str, limit: int = 10) -> Tuple[List[SearchResult], Optional[Exception]]:
    """Scrape YouTube search page for video results """

    results: List[SearchResult] = []
    search_query = urllib.parse.quote_plus(search_term)
    search_url = f"https://www.youtube.com/results?search_query={search_query}"
    try:
        response = HTTP_CLIENT.get(search_url, headers={"Accept-Language": "en", "User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
        
        body = response.text
        
        # 1. Extract JSON payload using the resilient parser
        json_data = extract_json_from_html(body)
        if not json_data:
            return [], Exception("Invalid response from YouTube: failed to extract ytInitialData.")
        
        # 2. Get Contents Block (Handle ad/carousel section skipping)
        contents_list = None
        index = 0
        while True:
            contents_list = get_content(json_data, index)
            if not contents_list:
                break
            # Check if the current section content is an ad/carousel renderer
            if contents_list[0].get("carouselAdRenderer") is not None:
                index += 1 
            else:
                break 
        if not contents_list:
             return [], Exception("Could not find main search results section in response.")
             
        # 3. Process Video Results
        for item in contents_list:
            if limit > 0 and len(results) >= limit:
                break
            renderer = item.get('videoRenderer')
            if not renderer:
                continue

            try:
                # Extract fields using direct JSON path translation
                video_id = renderer.get('videoId', '')
                title = renderer['title']['runs'][0]['text']
                uploader = renderer['ownerText']['runs'][0]['text']
                
                is_live = renderer.get('badges') is not None
                duration = renderer.get('lengthText', {}).get('simpleText', '')
                if is_live:
                    duration = "" 
                
                results.append(SearchResult(
                    Title=title,
                    Uploader=uploader,
                    Duration=duration,
                    ID=video_id,
                    URL=f"https://youtube.com/watch?v={video_id}",
                    Live=is_live,
                    SourceName="youtube",
                ))
            except (KeyError, IndexError, TypeError):
                continue
                
        return results, None

    except requests.exceptions.RequestException as e:
        return [], Exception(f"Cannot get youtube search page: {e}")
    except Exception as e:
        return [], Exception(f"Error during custom YouTube search: {e}")


# --- Main Logic ---
def GetYoutubeId(track: Track) -> Tuple[Optional[str], Optional[Exception]]:
    """
    Prioritizes duration match from custom search, with yt-dlp fallback.
    """
    song_duration_in_seconds = track.Duration
    search_query = f"'{track.Title}' {track.Artist}" 

    search_results, err = yt_search(search_query, 10)
    if err and "Invalid response" in str(err):
        # Fallback if the scraper fails due to YouTube structural change
        fallback_id = fallback_search_yt_dlp(track)
        if fallback_id:
            return fallback_id, None
        
        # If fallback also fails, return the original error
        return None, err


    if not search_results:
        # Fallback if the search returns no results
        fallback_id = fallback_search_yt_dlp(track)
        if fallback_id:
            return fallback_id, None

        error_message = f"no songs found for {search_query}"
        return None, Exception(error_message)
        
    # 1. Try for the closest match timestamp wise
    for result in search_results:
        if result.Live:
            continue
            
        result_song_duration = convert_string_duration_to_seconds(result.Duration)
        
        allowed_duration_range_start = song_duration_in_seconds - DURATION_MATCH_THRESHOLD
        allowed_duration_range_end = song_duration_in_seconds + DURATION_MATCH_THRESHOLD
        
        if (result_song_duration >= allowed_duration_range_start and 
            result_song_duration <= allowed_duration_range_end):
            
            logger.info(f"Found song with id '{result.ID}' (Duration Match)")
            return result.ID, None
            
    # 2. If duration match fails, use fallback before returning "not found"
    fallback_id = fallback_search_yt_dlp(track)
    if fallback_id:
        return fallback_id, None
            
    return None, Exception(f"could not settle on a song from search result for: {search_query}")