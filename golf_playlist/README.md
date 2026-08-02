# Golf Playlist (ATLiens / Camp mood filter)

A script that keeps a Spotify playlist tuned to the sound of OutKast's
*ATLiens* and Childish Gambino's *Camp*, filling toward a target length
(default 4 hours) and re-filtered toward whatever vibe you're after.

It's designed to be driven through chat with Claude rather than typed
manually: you describe a vibe ("laid-back Sunday round," "hype for the back
nine"), Claude translates that into target tempo/energy/valence/tone numbers
and runs the script for you. You never need a terminal for day-to-day use.
Mood presets (`--mood chill|hype|focused|upbeat`) are also available if you
want to run it directly.

Each run:

1. Builds a reference sound profile (tempo, energy, valence, danceability,
   acousticness, instrumentalness, speechiness) from the two reference
   albums.
2. Shifts that profile toward the requested mood and/or explicit
   `--target-*` overrides.
3. Pulls candidate tracks from a curated pool of sonically-similar artists
   (Kendrick Lamar, Anderson .Paak, Isaiah Rashad, The Roots, D'Angelo,
   etc. — see `SEED_ARTISTS` in `golf_playlist.py`), including album deep
   cuts, not just each artist's top 10.
4. Removes tracks already in the playlist that no longer fit, and adds
   fitting candidates until the playlist reaches `--duration-minutes`
   (default 240) or `--size` (optional track-count cap), whichever is
   tighter.

## One-time setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Create a Spotify API app:
   - Go to https://developer.spotify.com/dashboard and log in.
   - Click **Create app**.
   - Set a **Redirect URI** of `http://127.0.0.1:8080/callback` (must match
     exactly what you put in `.env` below — nothing needs to actually be
     listening on it).
   - Save, then open the app's settings to copy the **Client ID** and
     **Client Secret**.

3. Create a `.env` file in this directory:

   ```bash
   SPOTIPY_CLIENT_ID=your_client_id
   SPOTIPY_CLIENT_SECRET=your_client_secret
   SPOTIPY_REDIRECT_URI=http://127.0.0.1:8080/callback
   ```

4. Log in once, headlessly (no browser needed on this machine):

   ```bash
   python auth_setup.py --print-url
   ```

   Open the printed URL in your own browser, log in to Spotify, and approve
   access. You'll land on a page that likely fails to load — that's
   expected. Copy the full URL from your browser's address bar (it contains
   `?code=...`) and run:

   ```bash
   python auth_setup.py --code "<the URL you landed on>"
   ```

   This caches a token to `.spotify_cache`. From then on, `golf_playlist.py`
   refreshes it automatically — no more logins needed.

## Usage

```bash
python golf_playlist.py --mood chill
python golf_playlist.py --mood hype --duration-minutes 300
python golf_playlist.py --target-energy 0.72 --target-valence 0.55 --target-tempo 96 --dry-run
```

Options:

- `--mood {default,chill,hype,focused,upbeat}` — preset mood (default:
  `default`, i.e. just the raw ATLiens/Camp profile).
- `--target-energy`, `--target-valence`, `--target-danceability`,
  `--target-acousticness`, `--target-instrumentalness`,
  `--target-speechiness`, `--target-tempo` — explicit numeric overrides
  (0-1 scale, tempo in BPM), applied on top of the mood preset. This is
  what Claude uses to turn a free-text vibe description into concrete
  targets.
- `--playlist-name NAME` — playlist to create/update (default: `Golf Mix
  (ATLiens/Camp)`).
- `--duration-minutes N` — target total playlist length (default: `240`).
- `--size N` — optional hard cap on track count, in addition to duration.
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
