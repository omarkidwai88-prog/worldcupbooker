#!/usr/bin/env python3
"""One-time headless Spotify login. No browser or local server required here.

Step 1:
    python auth_setup.py --print-url
    -> Open the printed URL in your own browser, log in to Spotify, and
       approve access. You'll land on a page that likely fails to load
       (e.g. "can't reach this page") - that's expected, since nothing is
       listening on the redirect URI. What matters is the URL in your
       browser's address bar, which now contains an authorization code.

Step 2:
    python auth_setup.py --code "<the URL you landed on>"
    -> Paste the whole URL (or just the code= value). This exchanges it
       for an access token and caches it to .spotify_cache. Future runs of
       golf_playlist.py reuse and refresh that token automatically.
"""
import argparse
import os
import sys

from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

SCOPE = "playlist-modify-public playlist-modify-private playlist-read-private"


def get_oauth() -> SpotifyOAuth:
    load_dotenv()
    required = ["SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET", "SPOTIPY_REDIRECT_URI"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        sys.exit("Missing Spotify credentials: " + ", ".join(missing) + "\nSee README.md.")
    return SpotifyOAuth(scope=SCOPE, cache_path=".spotify_cache", open_browser=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--print-url", action="store_true", help="Print the authorization URL to visit")
    parser.add_argument("--code", help="The full redirect URL (or bare code) you landed on after approving access")
    args = parser.parse_args()

    oauth = get_oauth()

    if args.print_url:
        print(oauth.get_authorize_url())
        return

    if args.code:
        code = oauth.parse_response_code(args.code)
        oauth.get_access_token(code, as_dict=False, check_cache=False)
        print("Login cached to .spotify_cache. You're set - golf_playlist.py will now work.")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
