from typing import Dict
from app.models.model import Couple
from .redis_client import RedisClient
import threading

def _redis_store_fingerprints_background(
    redis_client: RedisClient,
    fingerprints: Dict[int, Couple],
) -> None:
    """
    Background task: write fingerprints to Redis after MongoDB has confirmed the write.
    Logs a warning on failure but does not raise
    """
    err = redis_client.StoreFingerprints(fingerprints)
    if err:
        print(f"[Hybrid Warning] Redis StoreFingerprints background task failed: {err}")



def schedule_redis_fingerprint_store(redis_client, fingerprints):
    t = threading.Thread(
        target=_redis_store_fingerprints_background,
        args=(redis_client, fingerprints),
        daemon=True
    )
    t.start()
    return t