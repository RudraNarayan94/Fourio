from typing import Dict, List, Tuple, Optional, Any

from app.models.model import Couple, Song, DBClient
from .mongo_client import NewMongoClient, MongoClient
from .redis_client import NewRedisClient, RedisClient
from .background_job import schedule_redis_fingerprint_store
class HybridClient(DBClient):
    """
    Hybrid DB client: Redis for speed, MongoDB for durability.
    """
    def __init__(self, redis_client: RedisClient, mongo_client: MongoClient):
        self._redis = redis_client
        self._mongo = mongo_client

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.Close()

    def Close(self) -> Optional[Exception]:
        err1 = self._redis.Close()
        err2 = self._mongo.Close()
        if err1:
            return err1
        if err2:
            return err2
        return None

    # ---------------- Songs ----------------
    def RegisterSong(self, songTitle: str, songArtist: str, ytID: str) -> Tuple[int, Optional[Exception]]:
        # Register in MongoDB (durable)
        songID, err = self._mongo.RegisterSong(songTitle, songArtist, ytID)
        if err:
            return 0, err
        # Push to Redis for fast lookup
        song, _, _ = self._mongo.GetSongByID(songID)
        if song:
            _, redis_err = self._redis.RegisterSong(song.Title, song.Artist, song.YouTubeID)
            if redis_err:
                print(f"[Hybrid Warning] Redis RegisterSong failed: {redis_err}")
        return songID, None

    def GetSong(self, filterKey: str, value: Any) -> Tuple[Optional[Song], bool, Optional[Exception]]:
        # Try Redis first
        song, found, err = self._redis.GetSong(filterKey, value)
        if found or err:
            return song, found, err
        # Fallback to MongoDB
        song, found, err = self._mongo.GetSong(filterKey, value)
        if found and song:
            # Ingest into Redis for next time
            _, redis_err = self._redis.RegisterSong(song.Title, song.Artist, song.YouTubeID)
            if redis_err:
                print(f"[Hybrid Warning] Redis ingest failed: {redis_err}")
        return song, found, err

    def GetSongByID(self, songID: int) -> Tuple[Optional[Song], bool, Optional[Exception]]:
        return self.GetSong("_id", songID)

    def GetSongByYTID(self, ytID: str) -> Tuple[Optional[Song], bool, Optional[Exception]]:
        return self.GetSong("ytID", ytID)

    def GetSongByKey(self, key: str) -> Tuple[Optional[Song], bool, Optional[Exception]]:
        return self.GetSong("key", key)

    def GetSongsByIDs(self, songIDs: List[int]) -> Tuple[Dict[int, Song], Optional[Exception]]:
        """Fetch multiple songs, trying Redis first then MongoDB."""
        if not songIDs:
            return {}, None
        
        songs_map = {}
        missing_ids = []
        
        # Try Redis first for each song
        for song_id in songIDs:
            song, found, err = self._redis.GetSongByID(song_id)
            if found and song:
                songs_map[song_id] = song
            else:
                missing_ids.append(song_id)
        
        # For missing songs, fetch from MongoDB
        if missing_ids:
            mongo_map, mongo_err = self._mongo.GetSongsByIDs(missing_ids)
            if mongo_err:
                print(f"[Hybrid Warning] MongoDB GetSongsByIDs failed: {mongo_err}")
            else:
                # Ingest missing songs into Redis for next time
                for song_id, song in mongo_map.items():
                    songs_map[song_id] = song
                    try:
                        self._redis.RegisterSong(song.Title, song.Artist, song.YouTubeID)
                    except Exception as e:
                        print(f"[Hybrid Warning] Redis ingest failed for song {song_id}: {e}")
        
        return songs_map, None

    def DeleteSongByID(self, songID: int) -> Optional[Exception]:
        err1 = self._redis.DeleteSongByID(songID)
        err2 = self._mongo.DeleteSongByID(songID)
        if err1:
            return err1
        return err2

    def TotalSongs(self) -> Tuple[int, Optional[Exception]]:
        # Prefer Redis for speed
        return self._redis.TotalSongs()

    # ---------------- Fingerprints ----------------
    def StoreFingerprints(self, fingerprints: Dict[int, Couple]) -> Optional[Exception]:
        err = self._mongo.StoreFingerprints(fingerprints)  # durable first
        if not err:
            schedule_redis_fingerprint_store(self._redis, fingerprints) 
        return None

    def GetCouples(self, addresses: List[int]) -> Tuple[Dict[int, List[Couple]], Optional[Exception]]:
        # Try Redis first
        couples_map, err = self._redis.GetCouples(addresses)
        missing_addresses = [a for a in addresses if a not in couples_map]
        if not missing_addresses:
            return couples_map, err

        # Fallback to MongoDB
        mongo_map, mongo_err = self._mongo.GetCouples(missing_addresses)
        couples_map.update(mongo_map)

        # Ingest missing into Redis for next time
        if mongo_map:
            try:
                pipe_data = {}
                for addr, couples in mongo_map.items():
                    pipe_data[addr] = couples
                self._redis.StoreFingerprints(pipe_data)
            except Exception as e:
                print(f"[Hybrid Warning] Redis ingest fingerprints failed: {e}")

        return couples_map, mongo_err or err

    def DeleteCollection(self, collectionName: str) -> Optional[Exception]:
        err1 = self._redis.DeleteCollection(collectionName)
        err2 = self._mongo.DeleteCollection(collectionName)
        if err1:
            return err1
        return err2


def NewHybridClient(dbUri: str, redisUri: str) -> Tuple[Optional[HybridClient], Optional[Exception]]:
    # Create Redis client
    redis_client, err = NewRedisClient(redisUri)
    if err:
        return None, err
    # Create Mongo client
    mongo_client, err = NewMongoClient(dbUri)
    if err:
        return None, err
    # Return hybrid
    return HybridClient(redis_client, mongo_client), None