"""Self-contained LLM interface for AI player interaction.

All LLM communication goes through this module. Currently uses dummy/static
responses — swap in real API calls later without changing any other files.
"""

import random

from rich.console import Console

console = Console()

# The AI player is always named "Claude"
AI_PLAYER_NAME = "Claude"

# Dummy day-phase responses the AI cycles through
_DAY_RESPONSES = [
    "Hmm, I'm not sure who the werewolf is, but something feels off.",
    "I think we should look more carefully at who's being too quiet.",
    "I have a feeling someone here isn't telling the truth.",
    "Let's think about this logically. Who has the most to gain from lying?",
    "I'm suspicious, but I want to hear what everyone else thinks first.",
]


def is_ai_player(player: str) -> bool:
    """Check whether a player name belongs to the AI."""
    return player == AI_PLAYER_NAME


def get_night_action(role: str, prompt: str, choices: list[str], context: str) -> str:
    """Choose a night action from the available options.

    Args:
        role: The AI's current role (e.g. "Seer", "Robber").
        prompt: The decision prompt (same text a human would see).
        choices: Available options to pick from.
        context: Game context string describing what the AI knows so far.

    Returns:
        One of the strings from choices.
    """
    # Dummy: pick a random choice
    choice = random.choice(choices)
    console.print(f"[dim]AI ({role}) chose: {choice}[/dim]")
    return choice


def get_checkbox_action(
    role: str, prompt: str, choices: list[str], count: int, context: str
) -> list[str]:
    """Choose multiple items from a list (e.g. Seer picking 2 center cards).

    Args:
        role: The AI's current role.
        prompt: The decision prompt.
        choices: Available options.
        count: Exactly how many to select.
        context: Game context string.

    Returns:
        A list of exactly `count` strings from choices.
    """
    # Dummy: pick the first `count` choices
    selected = choices[:count]
    console.print(f"[dim]AI ({role}) chose: {selected}[/dim]")
    return selected


def get_day_response(role: str, transcript: list[dict]) -> str:
    """Generate what the AI wants to say during the day discussion.

    Args:
        role: The AI's current role (from its perspective — may differ from
              actual current_roles if swapped, but the AI doesn't know that).
        transcript: The discussion transcript so far, as a list of dicts
                    with 'speaker' and 'text' keys.

    Returns:
        A string the AI wants to speak aloud.
    """
    # Dummy: cycle through static responses
    idx = len(transcript) % len(_DAY_RESPONSES)
    response = _DAY_RESPONSES[idx]
    console.print(f"[dim]AI says: {response}[/dim]")
    return response


def get_vote(role: str, choices: list[str], transcript: list[dict]) -> str:
    """Choose who to vote for during the voting phase.

    Args:
        role: The AI's current role (from its perspective).
        choices: Available vote targets (other players + "No one").
        transcript: The full discussion transcript for context.

    Returns:
        One of the strings from choices.
    """
    # Dummy: pick a random player (not "No one")
    player_choices = [c for c in choices if c != "No one"]
    choice = random.choice(player_choices) if player_choices else "No one"
    console.print(f"[dim]AI votes for: {choice}[/dim]")
    return choice
