#!/usr/bin/env python3
"""Keep a golf playlist tuned to the ATLiens/Camp sound, filtered by mood.

Run this whenever you want the playlist refreshed:

    python golf_playlist.py --mood chill
    python golf_playlist.py --target-energy 0.7 --target-valence 0.55 --target-tempo 96

It builds a target audio-feature profile from OutKast's ATLiens and Childish
Gambino's Camp, shifts that profile toward the requested mood (or explicit
--target-* overrides), then adds tracks from a curated pool of
sonically-similar artists that fit and removes tracks already in the
playlist that no longer fit, filling toward --duration-minutes (default 240,
i.e. 4 hours).

See README.md for one-time Spotify API setup (run auth_setup.py first).
"""
import argparse
import os
import sys

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

from moods import MOOD_PRESETS, apply_mood

SCOPE = "playlist-modify-public playlist-modify-private playlist-read-private"

REFERENCE_ALBUMS = [
    ("OutKast", "ATLiens"),
    ("Childish Gambino", "Camp"),
]

# Artists in the same sonic neighborhood as ATLiens/Camp: Southern and
# alt/conscious hip-hop with live-instrumentation and neo-soul touches.
SEED_ARTISTS = [
    "OutKast",
    "Childish Gambino",
    "Kendrick Lamar",
    "Anderson .Paak",
    "Isaiah Rashad",
    "The Roots",
    "Yasiin Bey",
    "Digable Planets",
    "De La Soul",
    "J. Cole",
    "Little Brother",
    "Erykah Badu",
    "D'Angelo",
]

FEATURE_KEYS = [
    "energy",
    "valence",
    "danceability",
    "acousticness",
    "instrumentalness",
    "speechiness",
    "tempo",
]

TEMPO_NORM = 200.0  # rough BPM scale to put tempo on a similar footing to 0-1 features


def get_spotify_client() -> spotipy.Spotify:
    load_dotenv()
    required = ["SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET", "SPOTIPY_REDIRECT_URI"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        sys.exit(
            "Missing Spotify credentials: "
            + ", ".join(missing)
            + "\nSee README.md for setup instructions."
        )
    auth_manager = SpotifyOAuth(scope=SCOPE, cache_path=".spotify_cache", open_browser=False)
    if not auth_manager.get_cached_token():
        sys.exit("No cached Spotify login found. Run auth_setup.py first (see README.md).")
    return spotipy.Spotify(auth_manager=auth_manager)


def build_reference_profile(sp: spotipy.Spotify) -> dict:
    track_ids = []
    for artist, album in REFERENCE_ALBUMS:
        result = sp.search(q=f"album:{album} artist:{artist}", type="album", limit=1)
        items = result["albums"]["items"]
        if not items:
            print(f"Warning: couldn't find album '{album}' by {artist}", file=sys.stderr)
            continue
        album_id = items[0]["id"]
        tracks = sp.album_tracks(album_id)["items"]
        track_ids.extend(t["id"] for t in tracks if t["id"])

    if not track_ids:
        sys.exit("Could not find any reference tracks; check network/credentials.")

    features = fetch_audio_features(sp, track_ids)
    return average_features(features)


def fetch_audio_features(sp: spotipy.Spotify, track_ids: list) -> list:
    features = []
    for i in range(0, len(track_ids), 100):
        batch = track_ids[i : i + 100]
        features.extend(f for f in sp.audio_features(batch) if f)
    return features


def average_features(features: list) -> dict:
    profile = {}
    for key in FEATURE_KEYS:
        values = [f[key] for f in features if f.get(key) is not None]
        profile[key] = sum(values) / len(values) if values else 0.0
    return profile


ALBUMS_PER_ARTIST = 5  # keeps API call volume reasonable while giving enough depth for a 4+ hour playlist


def build_candidate_pool(sp: spotipy.Spotify) -> dict:
    """Return {track_id: track_object} pulled from each seed artist's top tracks + a few albums."""
    candidates = {}
    for name in SEED_ARTISTS:
        result = sp.search(q=f"artist:{name}", type="artist", limit=1)
        items = result["artists"]["items"]
        if not items:
            print(f"Warning: couldn't find artist '{name}'", file=sys.stderr)
            continue
        artist_id = items[0]["id"]

        for track in sp.artist_top_tracks(artist_id)["tracks"]:
            candidates[track["id"]] = track

        albums = sp.artist_albums(artist_id, album_type="album", limit=ALBUMS_PER_ARTIST)["items"]
        for album in albums:
            for track in sp.album_tracks(album["id"])["items"]:
                if track["id"] not in candidates:
                    # album_tracks omits some fields (e.g. popularity) that top-tracks
                    # includes, but has everything scoring/adding a track needs.
                    candidates[track["id"]] = track
    return candidates


def distance(profile: dict, features: dict) -> float:
    total = 0.0
    for key in FEATURE_KEYS:
        a = profile[key]
        b = features[key]
        if key == "tempo":
            a, b = a / TEMPO_NORM, b / TEMPO_NORM
        total += (a - b) ** 2
    return total ** 0.5


def get_or_create_playlist(sp: spotipy.Spotify, user_id: str, name: str) -> str:
    playlists = sp.current_user_playlists(limit=50)["items"]
    for pl in playlists:
        if pl["name"] == name:
            return pl["id"]
    playlist = sp.user_playlist_create(user_id, name, public=False, description="ATLiens/Camp golf mix")
    return playlist["id"]


def get_playlist_tracks(sp: spotipy.Spotify, playlist_id: str) -> dict:
    """Return {track_id: duration_ms} for every track currently in the playlist."""
    tracks = {}
    results = sp.playlist_items(playlist_id, fields="items.track.id,items.track.duration_ms,next")
    while results:
        for item in results["items"]:
            if item["track"]:
                tracks[item["track"]["id"]] = item["track"]["duration_ms"]
        results = sp.next(results) if results.get("next") else None
    return tracks


TARGET_OVERRIDE_FLAGS = {
    "target_energy": "energy",
    "target_valence": "valence",
    "target_danceability": "danceability",
    "target_acousticness": "acousticness",
    "target_instrumentalness": "instrumentalness",
    "target_speechiness": "speechiness",
    "target_tempo": "tempo",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mood",
        choices=sorted(MOOD_PRESETS),
        default="default",
        help="Mood preset to filter toward within the ATLiens/Camp sound (default: %(default)s)",
    )
    parser.add_argument("--playlist-name", default="Golf Mix (ATLiens/Camp)")
    parser.add_argument(
        "--duration-minutes",
        type=float,
        default=240,
        help="Target total playlist length in minutes (default: %(default)s, i.e. 4 hours)",
    )
    parser.add_argument("--size", type=int, help="Optional hard cap on track count, in addition to duration")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.35,
        help="Max distance from the target profile for a track to be kept (default: %(default)s)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print planned changes without touching the playlist")
    for flag, feature_key in TARGET_OVERRIDE_FLAGS.items():
        parser.add_argument(
            f"--{flag.replace('_', '-')}",
            type=float,
            dest=flag,
            help=f"Explicit target {feature_key} value, overriding the mood preset",
        )
    args = parser.parse_args()

    sp = get_spotify_client()
    user_id = sp.current_user()["id"]

    print("Building reference sound profile from ATLiens + Camp...")
    baseline = build_reference_profile(sp)
    target = apply_mood(baseline, args.mood)
    for flag, feature_key in TARGET_OVERRIDE_FLAGS.items():
        value = getattr(args, flag)
        if value is not None:
            target[feature_key] = value
    print("Target profile: " + ", ".join(f"{k}={v:.2f}" for k, v in target.items()))

    playlist_id = get_or_create_playlist(sp, user_id, args.playlist_name)
    existing = get_playlist_tracks(sp, playlist_id)
    existing_ids = list(existing)

    print("Scoring existing playlist tracks against the target profile...")
    existing_features = {f["id"]: f for f in fetch_audio_features(sp, existing_ids) if f}
    to_remove = [
        tid for tid in existing_ids
        if tid in existing_features and distance(target, existing_features[tid]) > args.threshold
    ]
    kept_duration_ms = sum(existing[tid] for tid in existing_ids if tid not in to_remove)

    print("Scoring candidate pool (this pulls each seed artist's top tracks + a few albums)...")
    candidates = build_candidate_pool(sp)
    candidate_ids = [tid for tid in candidates if tid not in existing_ids]
    candidate_features = {f["id"]: f for f in fetch_audio_features(sp, candidate_ids) if f}

    scored = sorted(
        (
            (distance(target, feats), tid)
            for tid, feats in candidate_features.items()
            if distance(target, feats) <= args.threshold
        ),
        key=lambda pair: pair[0],
    )

    target_duration_ms = args.duration_minutes * 60_000
    to_add = []
    total_duration_ms = kept_duration_ms
    for _, tid in scored:
        if total_duration_ms >= target_duration_ms:
            break
        if args.size is not None and len(existing_ids) - len(to_remove) + len(to_add) >= args.size:
            break
        to_add.append(tid)
        total_duration_ms += candidates[tid].get("duration_ms", 0)

    print(f"Removing {len(to_remove)} track(s) that no longer fit.")
    for tid in to_remove:
        print(f"  - {candidates.get(tid, {}).get('name', tid)}")
    print(f"Adding {len(to_add)} track(s) that fit "
          f"(playlist will run ~{total_duration_ms / 60_000:.0f} min).")
    for tid in to_add:
        track = candidates[tid]
        artists = ", ".join(a["name"] for a in track["artists"])
        print(f"  + {track['name']} - {artists}")

    if args.dry_run:
        print("Dry run: no changes made.")
        return

    if to_remove:
        sp.playlist_remove_all_occurrences_of_items(playlist_id, to_remove)
    if to_add:
        sp.playlist_add_items(playlist_id, to_add)
    print("Done.")


if __name__ == "__main__":
    main()
