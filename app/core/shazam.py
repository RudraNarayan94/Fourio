import time
import math
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
from app.models.model import Match 
from app.db.db_clients import NewDBClient
from .fingerprint import Fingerprint, TARGET_ZONE_SIZE
from app.utils.utils import GenerateUniqueID
from app.utils.logger_setup import GetLogger
from .spectrogram import Spectrogram, ExtractPeaks

def analyze_relative_timing(matches: Dict[int, List[Tuple[int, int]]]) -> Dict[int, float]:
    """
    Calculates a score based on the consistency of relative timing between sample and database.
    """
    scores: Dict[int, float] = {}
    tolerance_ms = 100  
    
    for song_id, times in matches.items():
        count = 0
        N = len(times)
        
        for i in range(N):
            for j in range(i + 1, N):
                sample_time_i, db_time_i = times[i]
                sample_time_j, db_time_j = times[j]
                
                sample_diff = abs(float(sample_time_i - sample_time_j))
                db_diff = abs(float(db_time_i - db_time_j))
                
                if math.fabs(sample_diff - db_diff) < tolerance_ms:
                    count += 1
                    
        scores[song_id] = float(count)
        
    return scores

def filter_matches(
    threshold: int,
    matches: Dict[int, List[Tuple[int, int]]],
    target_zones: Dict[int, Dict[int, int]]
) -> Dict[int, List[Tuple[int, int]]]:
    """
    Filters out songs that don't have enough verified target zones.
    """
    
    # 1. Filter out non-target zones (count < TARGET_ZONE_SIZE)
    for song_id, anchor_times in target_zones.items():
        keys_to_delete = [anchor_time for anchor_time, count in anchor_times.items() 
                          if count < TARGET_ZONE_SIZE]
        if keys_to_delete:
            print(f"  [filter_matches] Song {song_id}: Removing {len(keys_to_delete)} zones (low couple count)")
        for key in keys_to_delete:
             del target_zones[song_id][key]

    filtered_matches: Dict[int, List[Tuple[int, int]]] = {}
    for song_id, zones in target_zones.items():
        # if the number of remaining valid target zones meets the threshold
        if len(zones) >= threshold:
            filtered_matches[song_id] = matches[song_id]
            print(f"  [filter_matches] Song {song_id}: PASSED (has {len(zones)} valid zones, threshold={threshold})")
        else:
            print(f"  [filter_matches] Song {song_id}: FILTERED OUT (only {len(zones)} valid zones, threshold={threshold})")

    return filtered_matches

# --- Main Matcher Functions ---

def FindMatchesFGP(sample_fingerprint: Dict[int, int]) -> Tuple[List[Match], float, Optional[Exception]]:
    """
    Uses the sample fingerprint (address -> sampleTime) 
    to find and score matches in the database.
    """
    start_time = time.perf_counter()
    logger = GetLogger()

    print(f"[FindMatchesFGP DEBUG] Starting matching process...")
    print(f"[FindMatchesFGP DEBUG] Total fingerprint addresses: {len(sample_fingerprint)}")
    
    MAX_ADDRESSES = 2000 #adjust as needed
    all_addresses = list(sample_fingerprint.keys())
    
    if len(all_addresses) > MAX_ADDRESSES:
        step = len(all_addresses) // MAX_ADDRESSES
        addresses = all_addresses[::step]
        print(f"[FindMatchesFGP DEBUG] Sampled {len(addresses)} addresses from {len(all_addresses)} total (step={step})")
        logger.info(f"Sampled {len(addresses)} addresses from {len(all_addresses)} total")
    else:
        addresses = all_addresses
        print(f"[FindMatchesFGP DEBUG] Using all {len(addresses)} addresses (under limit)")

    db_client, err = NewDBClient()
    if err: 
        return None, time.perf_counter() - start_time, err
    
    # 'with'  handles  db.Close()
    with db_client: 
        print(f"[FindMatchesFGP DEBUG] Querying database for {len(addresses)} addresses...")
        query_start = time.perf_counter()
        
        m, err = db_client.GetCouples(addresses) # Dict[address, List[Couple]]
        
        query_time = time.perf_counter() - query_start
        print(f"[FindMatchesFGP DEBUG] Database query completed in {query_time:.4f} seconds")
        print(f"[FindMatchesFGP DEBUG] Retrieved {len(m)} matching addresses from DB")
        
        if err: 
            return None, time.perf_counter() - start_time, err

        # Calculate total couples retrieved
        total_couples = sum(len(couples) for couples in m.values())
        print(f"[FindMatchesFGP DEBUG] Total couples retrieved: {total_couples}")

        # songID -> [(sampleTime, dbTime)]
        matches: Dict[int, List[Tuple[int, int]]] = defaultdict(list) 
        # songID -> earliest anchor time in DB
        timestamps: Dict[int, int] = {} 
        # songID -> {timestamp: count} (Used for filterMatches)
        target_zones: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int)) 

        print(f"[FindMatchesFGP DEBUG] Processing matches...")
        process_start = time.perf_counter()
        
        # process Matches and Timing
        for address, couples in m.items():
            sample_time_ms = sample_fingerprint[address]
            
            for couple in couples:
                song_id = couple.SongID
                db_time_ms = couple.AnchorTimeMs
                
                matches[song_id].append((sample_time_ms, db_time_ms))

                # find the earliest timestamp (for final match output)
                if song_id not in timestamps or db_time_ms < timestamps[song_id]:
                    timestamps[song_id] = db_time_ms

                target_zones[song_id][db_time_ms] += 1

        process_time = time.perf_counter() - process_start
        print(f"[FindMatchesFGP DEBUG] Match processing completed in {process_time:.4f} seconds")
        print(f"[FindMatchesFGP DEBUG] Found {len(matches)} unique songs with matches")

        # Filter Matches
        print(f"[FindMatchesFGP DEBUG] Before filtering: {len(matches)} songs have potential matches")
        for song_id in matches.keys():
            valid_zones = len(target_zones[song_id])
            print(f"  Song {song_id}: {valid_zones} valid target zones, {len(matches[song_id])} couple matches")
        
        # matches = filter_matches(10, matches, target_zones)
        matches = filter_matches(4, matches, target_zones)
        
        print(f"[FindMatchesFGP DEBUG] After filtering (threshold=4): {len(matches)} songs remain")

        # analyze Relative Timing (Scoring)
        print(f"[FindMatchesFGP DEBUG] Analyzing relative timing and scoring...")
        scoring_start = time.perf_counter()
        
        scores = analyze_relative_timing(matches)
        
        scoring_time = time.perf_counter() - scoring_start
        print(f"[FindMatchesFGP DEBUG] Scoring completed in {scoring_time:.4f} seconds")
        print(f"[FindMatchesFGP DEBUG] Scored {len(scores)} songs")

        # BATCH FETCH: Get all songs in one MongoDB query
        song_ids = list(scores.keys())
        print(f"[FindMatchesFGP DEBUG] Fetching song details for {len(song_ids)} songs...")
        fetch_start = time.perf_counter()
        
        songs_map, err = db_client.GetSongsByIDs(song_ids)
        
        fetch_time = time.perf_counter() - fetch_start
        print(f"[FindMatchesFGP DEBUG] Song fetch completed in {fetch_time:.4f} seconds")
        print(f"[FindMatchesFGP DEBUG] Retrieved {len(songs_map)} song details")
        
        if err:
            logger.error(f"Failed to fetch songs: {err}")
            return None, time.perf_counter() - start_time, err
        
        # Build Final Match List
        print(f"[FindMatchesFGP DEBUG] Building final match list...")
        match_list: List[Match] = []
        skipped_songs = 0
        
        for song_id, score in scores.items():
            song = songs_map.get(song_id)
            
            if not song:
                logger.info(f"song with ID ({song_id}) doesn't exist")
                skipped_songs += 1
                continue

            match = Match(
                SongID=song_id,
                SongTitle=song.Title,
                SongArtist=song.Artist,
                YouTubeID=song.YouTubeID,
                Timestamp=timestamps.get(song_id, 0),
                Score=score
            )
            match_list.append(match)

        if skipped_songs > 0:
            print(f"[FindMatchesFGP DEBUG] Skipped {skipped_songs} songs (not found in DB)")

        # sort Matches by Score
        print(f"[FindMatchesFGP DEBUG] Sorting {len(match_list)} matches by score...")
        match_list.sort(key=lambda m: m.Score, reverse=True)
        
        if match_list:
            print(f"[FindMatchesFGP DEBUG] Top match: '{match_list[0].SongTitle}' by {match_list[0].SongArtist} (Score: {match_list[0].Score})")
            if len(match_list) > 1:
                print(f"[FindMatchesFGP DEBUG] 2nd match: '{match_list[1].SongTitle}' by {match_list[1].SongArtist} (Score: {match_list[1].Score})")

    total_time = time.perf_counter() - start_time
    print(f"[FindMatchesFGP DEBUG] Total matching process completed in {total_time:.4f} seconds")
    print(f"[FindMatchesFGP DEBUG] Breakdown:")
    print(f"  - DB Query: {query_time:.4f}s ({query_time/total_time*100:.1f}%)")
    print(f"  - Processing: {process_time:.4f}s ({process_time/total_time*100:.1f}%)")
    print(f"  - Scoring: {scoring_time:.4f}s ({scoring_time/total_time*100:.1f}%)")
    print(f"  - Fetch Songs: {fetch_time:.4f}s ({fetch_time/total_time*100:.1f}%)")
    
    return match_list, time.perf_counter() - start_time, None

def FindMatches(audio_sample: List[float], audio_duration: float, sample_rate: int) -> Tuple[List[Match], float, Optional[Exception]]:
    """
    Corresponds to the Go FindMatches function (Full DSP -> Fingerprint -> Match process).
    """
    start_time = time.perf_counter()

    # 1. DSP Pipeline
    spectrogram, err = Spectrogram(audio_sample, sample_rate)
    if err: return None, time.perf_counter() - start_time, Exception(f"failed to get spectrogram of samples: {err}")

    peaks = ExtractPeaks(spectrogram, audio_duration)
    
    # 2. Fingerprinting
    sample_id_placeholder = GenerateUniqueID() 
    sample_fingerprint = Fingerprint(peaks, sample_id_placeholder) 

    # Prepare map: address (hash) -> anchorTimeMs (time in sample)
    sample_fingerprint_map: Dict[int, int] = {
        address: couple.AnchorTimeMs 
        for address, couple in sample_fingerprint.items()
    }

    # 3. Matching
    # The duration returned is the duration of FindMatchesFGP, but we return the total duration
    matches, _, err = FindMatchesFGP(sample_fingerprint_map) 

    return matches, time.perf_counter() - start_time, None