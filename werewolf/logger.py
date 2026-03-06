"""Game transcript logger — writes completed game records to a JSON file."""

import json
import os
from copy import deepcopy
from datetime import datetime
from dataclasses import asdict

TRANSCRIPT_FILE = "game_transcripts.json"


def _load_transcripts(path: str) -> list[dict]:
    """Load existing transcripts from file, or return empty list if missing/corrupt."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _snapshot_state(state) -> dict:
    """Capture a serializable snapshot of a GameState."""
    return {
        "players": list(state.players),
        "original_roles": dict(state.original_roles),
        "current_roles": dict(state.current_roles),
        "center_cards": list(state.center_cards),
        "night_log": list(state.night_log),
        "discussion_transcript": list(state.discussion_transcript),
    }


def log_game(starting_state, ending_state, votes: dict[str, str], winner: str):
    """Append a completed game record to the transcripts file.

    :param starting_state: GameState snapshot taken after setup (before night).
    :param ending_state: GameState snapshot taken after all phases complete.
    :param votes: Mapping of player -> who they voted for.
    :param winner: The winning team/role string ('Village', 'Werewolf', 'Tanner').
    """
    record = {
        "timestamp": datetime.now().isoformat(),
        "starting_state": _snapshot_state(starting_state),
        "ending_state": _snapshot_state(ending_state),
        "votes": votes,
        "winner": winner,
    }

    transcripts = _load_transcripts(TRANSCRIPT_FILE)
    transcripts.append(record)

    with open(TRANSCRIPT_FILE, "w") as f:
        json.dump(transcripts, f, indent=2)
