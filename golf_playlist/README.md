# Golf Playlist (ATLiens / Camp mood filter)

A CLI script that keeps a Spotify playlist tuned to the sound of OutKast's
*ATLiens* and Childish Gambino's *Camp*, and re-filters it toward a mood you
pick each time you run it (`chill`, `hype`, `focused`, `upbeat`, or
`default`).

Each run:

1. Builds a reference sound profile (tempo, energy, valence, danceability,
   acousticness, instrumentalness, speechiness) from the two reference
   albums.
2. Shifts that profile toward the mood you asked for.
3. Pulls candidate tracks from a curated pool of sonically-similar artists
   (Kendrick Lamar, Anderson .Paak, Isaiah Rashad, The Roots, D'Angelo,
   etc. — see `SEED_ARTISTS` in `golf_playlist.py`).
4. Removes tracks already in the playlist that no longer fit the mood, and
   adds fitting candidates, up to `--size` total tracks.

Nothing runs on a schedule — you run it whenever you want the playlist
refreshed for your current mood.

## One-time setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Create a Spotify API app:
   - Go to https://developer.spotify.com/dashboard and log in.
   - Click **Create app**.
   - Set a **Redirect URI** of `http://127.0.0.1:8080/callback` (must match
     exactly what you put in `.env` below).
   - Save, then open the app's settings to copy the **Client ID** and
     **Client Secret**.

3. Create a `.env` file in this directory:

   ```bash
   SPOTIPY_CLIENT_ID=your_client_id
   SPOTIPY_CLIENT_SECRET=your_client_secret
   SPOTIPY_REDIRECT_URI=http://127.0.0.1:8080/callback
   ```

4. First run will open a browser window for you to log in and authorize the
   app; after that, a token cache (`.spotify_cache`) keeps you logged in.

## Usage

```bash
python golf_playlist.py --mood chill
python golf_playlist.py --mood hype --size 60
python golf_playlist.py --mood focused --dry-run   # preview without changing the playlist
```

Options:

- `--mood {default,chill,hype,focused,upbeat}` — target mood (default:
  `default`, i.e. just the raw ATLiens/Camp profile).
- `--playlist-name NAME` — playlist to create/update (default: `Golf Mix
  (ATLiens/Camp)`).
- `--size N` — target track count (default: `40`).
- `--threshold X` — how strict the sonic match needs to be, lower = pickier
  (default: `0.35`).
- `--dry-run` — print what would be added/removed without touching the
  playlist.

## Known limitation

Spotify tightened API access in late 2024: the audio-features endpoint this
script relies on is only available to apps with extended API access. Newly
created developer apps in the default "Development Mode" quota may get a 403
from `sp.audio_features(...)`. If that happens, request extended quota mode
for your app in the Spotify developer dashboard (Settings → extend quota
request) — for personal use this is normally approved quickly.
