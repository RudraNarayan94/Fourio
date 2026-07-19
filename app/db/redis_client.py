import redis
from typing import Dict, List, Tuple, Optional, Any
import json

from app.models.model import Couple, Song, DBClient
from app.utils.utils import GenerateUniqueID, GenerateSongKey

# --- constants ---
REDIS_SONGS_KEY = "songs"          # hash: songID -> song JSON
REDIS_FINGERPRINT_PREFIX = "fp:"   # key per address: fp:<address> -> list of couples


class RedisClient(DBClient):
    def __init__(self, client: redis.Redis):
        self._client = client

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.Close()

    def Close(self) -> Optional[Exception]:
        try:
            self._client.close()
            return None
        except Exception as e:
            return e

    # ---------------- Songs ----------------
    def RegisterSong(self, songTitle: str, songArtist: str, ytID: str) -> Tuple[int, Optional[Exception]]:
        try:
            songID = GenerateUniqueID()
            key = GenerateSongKey(songTitle, songArtist)

            # Check for duplicate by ytID or key
            for s in self._client.hvals(REDIS_SONGS_KEY):
                song_data = json.loads(s)
                if song_data.get("ytID") == ytID or song_data.get("key") == key:
                    return 0, Exception("song with ytID or key already exists")

            song_obj = {
                "_id": songID,
                "Title": songTitle,
                "Artist": songArtist,
                "ytID": ytID,
                "key": key
            }
            self._client.hset(REDIS_SONGS_KEY, songID, json.dumps(song_obj))
            return songID, None
        except Exception as e:
            return 0, e

    def GetSong(self, filterKey: str, value: Any) -> Tuple[Optional[Song], bool, Optional[Exception]]:
        try:
            for s in self._client.hvals(REDIS_SONGS_KEY):
                song_data = json.loads(s)
                if filterKey in song_data and song_data[filterKey] == value:
                    song_instance = Song(
                        Title=song_data["Title"],
                        Artist=song_data["Artist"],
                        YouTubeID=song_data["ytID"]
                    )
                    return song_instance, True, None
            return None, False, None
        except Exception as e:
            return None, False, e

    def GetSongByID(self, songID: int) -> Tuple[Optional[Song], bool, Optional[Exception]]:
        return self.GetSong("_id", songID)

    def GetSongByYTID(self, ytID: str) -> Tuple[Optional[Song], bool, Optional[Exception]]:
        return self.GetSong("ytID", ytID)

    def GetSongByKey(self, key: str) -> Tuple[Optional[Song], bool, Optional[Exception]]:
        return self.GetSong("key", key)

    def DeleteSongByID(self, songID: int) -> Optional[Exception]:
        try:
            self._client.hdel(REDIS_SONGS_KEY, songID)
            return None
        except Exception as e:
            return e

    def TotalSongs(self) -> Tuple[int, Optional[Exception]]:
        try:
            return self._client.hlen(REDIS_SONGS_KEY), None
        except Exception as e:
            return 0, e

    # ---------------- Fingerprints ----------------
    def StoreFingerprints(self, fingerprints: Dict[int, Couple], batch_size: int = 5000) -> Optional[Exception]:
      """
      Store fingerprints in Redis using pipelines in chunks to prevent
      memory overload or long-running single pipeline.
      
      """
      try:
          items = list(fingerprints.items())
          total = len(items)
          for i in range(0, total, batch_size):
              chunk = items[i:i + batch_size]
              pipe = self._client.pipeline()
              for address, couple in chunk:
                  key = f"{REDIS_FINGERPRINT_PREFIX}{address}"
                  pipe.rpush(key, json.dumps({"AnchorTimeMs": couple.AnchorTimeMs, "SongID": couple.SongID}))
              pipe.execute()
          return None
      except Exception as e:
          return e

    def GetCouples(self, addresses: List[int]) -> Tuple[Dict[int, List[Couple]], Optional[Exception]]:
        couples_map: Dict[int, List[Couple]] = {}
        try:
            pipe = self._client.pipeline()
            for address in addresses:
                pipe.lrange(f"{REDIS_FINGERPRINT_PREFIX}{address}", 0, -1)
            results = pipe.execute()
            for address, couples_json in zip(addresses, results):
                couples_list = [Couple(**json.loads(c)) for c in couples_json]
                couples_map[address] = couples_list
            return couples_map, None
        except Exception as e:
            return {}, e

    # ---------------- Utility ----------------
    def DeleteCollection(self, collectionName: str) -> Optional[Exception]:
        try:
            if collectionName == "songs":
                self._client.delete(REDIS_SONGS_KEY)
            elif collectionName == "fingerprints":
                keys = self._client.keys(f"{REDIS_FINGERPRINT_PREFIX}*")
                if keys:
                    self._client.delete(*keys)
            return None
        except Exception as e:
            return e


# --- factory method ---
def NewRedisClient(redis_url: str, host: str = "redis", port: int = 6379, db: int = 0) -> Tuple[Optional[RedisClient], Optional[Exception]]:
    try:
        if redis_url:
            client = redis.Redis.from_url(redis_url, decode_responses=True)
        else:
            client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        client.ping()
        return RedisClient(client), None
    except Exception as e:
        return None, e