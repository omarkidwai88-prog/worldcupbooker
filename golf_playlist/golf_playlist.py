#!/usr/bin/env python3
"""Keep a golf playlist tuned to the ATLiens/Camp sound, filtered by mood.

Run this whenever you want the playlist refreshed:

    python golf_playlist.py --mood chill

It builds a target audio-feature profile from OutKast's ATLiens and Childish
Gambino's Camp, shifts that profile toward the requested mood, then adds
tracks from a curated pool of sonically-similar artists that fit and removes
tracks already in the playlist that no longer fit.

See README.md for one-time Spotify API setup.
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
    auth_manager = SpotifyOAuth(scope=SCOPE, cache_path=".spotify_cache")
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


def build_candidate_pool(sp: spotipy.Spotify) -> dict:
    """Return {track_id: track_object} pulled from each seed artist's top tracks."""
    candidates = {}
    for name in SEED_ARTISTS:
        result = sp.search(q=f"artist:{name}", type="artist", limit=1)
        items = result["artists"]["items"]
        if not items:
            print(f"Warning: couldn't find artist '{name}'", file=sys.stderr)
            continue
        artist_id = items[0]["id"]
        top = sp.artist_top_tracks(artist_id)["tracks"]
        for track in top:
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


def get_playlist_track_ids(sp: spotipy.Spotify, playlist_id: str) -> list:
    ids = []
    results = sp.playlist_items(playlist_id, fields="items.track.id,next")
    while results:
        ids.extend(item["track"]["id"] for item in results["items"] if item["track"])
        results = sp.next(results) if results.get("next") else None
    return ids


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mood",
        choices=sorted(MOOD_PRESETS),
        default="default",
        help="Mood to filter toward within the ATLiens/Camp sound (default: %(default)s)",
    )
    parser.add_argument("--playlist-name", default="Golf Mix (ATLiens/Camp)")
    parser.add_argument("--size", type=int, default=40, help="Target track count")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.35,
        help="Max distance from the mood profile for a track to be kept (default: %(default)s)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print planned changes without touching the playlist")
    args = parser.parse_args()

    sp = get_spotify_client()
    user_id = sp.current_user()["id"]

    print("Building reference sound profile from ATLiens + Camp...")
    baseline = build_reference_profile(sp)
    target = apply_mood(baseline, args.mood)
    print(f"Target profile ({args.mood}): " + ", ".join(f"{k}={v:.2f}" for k, v in target.items()))

    playlist_id = get_or_create_playlist(sp, user_id, args.playlist_name)
    existing_ids = get_playlist_track_ids(sp, playlist_id)

    print("Scoring existing playlist tracks against the mood profile...")
    existing_features = {f["id"]: f for f in fetch_audio_features(sp, existing_ids) if f}
    to_remove = [
        tid for tid in existing_ids
        if tid in existing_features and distance(target, existing_features[tid]) > args.threshold
    ]

    print("Scoring candidate pool...")
    candidates = build_candidate_pool(sp)
    candidate_ids = [tid for tid in candidates if tid not in existing_ids]
    candidate_features = {f["id"]: f for f in fetch_audio_features(sp, candidate_ids) if f}

    scored = sorted(
        (
            (distance(target, feats), tid)
            for tid, feats in candidate_features.items()
        ),
        key=lambda pair: pair[0],
    )
    keep_count = max(0, args.size - (len(existing_ids) - len(to_remove)))
    to_add = [tid for dist, tid in scored if dist <= args.threshold][:keep_count]

    print(f"Removing {len(to_remove)} track(s) that no longer fit the '{args.mood}' mood.")
    for tid in to_remove:
        print(f"  - {candidates.get(tid, {}).get('name', tid)}")
    print(f"Adding {len(to_add)} track(s) that fit the '{args.mood}' mood.")
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
