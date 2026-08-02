"""Mood presets: deltas applied to the ATLiens/Camp reference sound profile.

Values are added to the baseline (derived at runtime from the reference
albums) and then clamped into valid ranges. Tempo is in BPM; every other
field is a 0-1 Spotify audio-feature value.
"""

MOOD_PRESETS = {
    "default": {},
    "chill": {
        "energy": -0.15,
        "tempo": -10,
        "acousticness": 0.10,
    },
    "hype": {
        "energy": 0.20,
        "valence": 0.10,
        "tempo": 12,
        "acousticness": -0.10,
    },
    "focused": {
        "energy": -0.05,
        "valence": -0.10,
        "instrumentalness": 0.15,
        "speechiness": -0.05,
    },
    "upbeat": {
        "valence": 0.20,
        "energy": 0.10,
        "tempo": 5,
    },
}

FEATURE_BOUNDS = {
    "energy": (0.0, 1.0),
    "valence": (0.0, 1.0),
    "danceability": (0.0, 1.0),
    "acousticness": (0.0, 1.0),
    "instrumentalness": (0.0, 1.0),
    "speechiness": (0.0, 1.0),
    "tempo": (60.0, 220.0),
}


def apply_mood(baseline: dict, mood: str) -> dict:
    if mood not in MOOD_PRESETS:
        valid = ", ".join(sorted(MOOD_PRESETS))
        raise ValueError(f"Unknown mood '{mood}'. Choose from: {valid}")

    deltas = MOOD_PRESETS[mood]
    target = dict(baseline)
    for key, delta in deltas.items():
        lo, hi = FEATURE_BOUNDS[key]
        target[key] = max(lo, min(hi, target.get(key, (lo + hi) / 2) + delta))
    return target
