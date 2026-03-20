"""LLM abstract interface for AI player interaction.

Defines the LLM ABC and provides module-level wrapper functions that
delegate to a global instance. Other modules import these wrappers
directly, so swapping the LLM provider only requires changing the
instance set via set_llm() in main.py.
"""

import random
from abc import ABC, abstractmethod

from rich.console import Console

console = Console()

# The AI player is always named "Claude"
AI_PLAYER_NAME = "Claude"

# Global LLM instance — set once at startup via set_llm()
_instance: "LLM | None" = None

# Fallback day responses when no LLM is configured
_FALLBACK_RESPONSES = [
    "Hmm, I'm not sure who the werewolf is, but something feels off.",
    "I think we should look more carefully at who's being too quiet.",
    "I have a feeling someone here isn't telling the truth.",
    "Let's think about this logically. Who has the most to gain from lying?",
    "I'm suspicious, but I want to hear what everyone else thinks first.",
]


class LLM(ABC):
    """Abstract base class for LLM providers.

    Each method corresponds to a game interaction point. Implementations
    handle their own API communication, conversation history, and error
    recovery.
    """

    @abstractmethod
    def reset_conversation(self) -> None:
        """Clear conversation history for a new game."""

    @abstractmethod
    def notify_role(self, role: str, players: list[str]) -> None:
        """Seed the conversation with the AI's role and player list."""

    @abstractmethod
    def notify_night_result(self, message: str) -> None:
        """Feed a night action outcome into the conversation history."""

    @abstractmethod
    def get_night_action(self, role: str, prompt: str, choices: list[str], context: str) -> str:
        """Choose a night action from the available options."""

    @abstractmethod
    def get_checkbox_action(
        self, role: str, prompt: str, choices: list[str], count: int, context: str
    ) -> list[str]:
        """Choose multiple items from a list."""

    @abstractmethod
    def get_day_response(self, role: str, transcript: list[dict]) -> str:
        """Generate what the AI wants to say during the day discussion."""

    @abstractmethod
    def get_vote(self, role: str, choices: list[str], transcript: list[dict]) -> str:
        """Choose who to vote for during the voting phase."""


# Module-level API

def set_llm(instance: LLM) -> None:
    """Set the global LLM instance used by all game modules."""
    global _instance
    _instance = instance


def is_ai_player(player: str) -> bool:
    """Check whether a player name belongs to the AI."""
    return player == AI_PLAYER_NAME


def reset_conversation() -> None:
    """Clear the conversation history for a new game."""
    if _instance is not None:
        _instance.reset_conversation()


def notify_role(role: str, players: list[str]) -> None:
    """Seed the conversation with the AI's role and player list."""
    if _instance is not None:
        _instance.notify_role(role, players)


def notify_night_result(message: str) -> None:
    """Feed a night action outcome into the conversation history."""
    if _instance is not None:
        _instance.notify_night_result(message)


def get_night_action(role: str, prompt: str, choices: list[str], context: str) -> str:
    """Choose a night action from the available options."""
    if _instance is not None:
        return _instance.get_night_action(role, prompt, choices, context)
    choice = random.choice(choices)
    console.print(f"[dim]AI ({role}) chose: {choice} (no LLM)[/dim]")
    return choice


def get_checkbox_action(
    role: str, prompt: str, choices: list[str], count: int, context: str
) -> list[str]:
    """Choose multiple items from a list."""
    if _instance is not None:
        return _instance.get_checkbox_action(role, prompt, choices, count, context)
    selected = choices[:count]
    console.print(f"[dim]AI ({role}) chose: {selected} (no LLM)[/dim]")
    return selected


def get_day_response(role: str, transcript: list[dict]) -> str:
    """Generate what the AI wants to say during the day discussion."""
    if _instance is not None:
        return _instance.get_day_response(role, transcript)
    idx = len(transcript) % len(_FALLBACK_RESPONSES)
    response = _FALLBACK_RESPONSES[idx]
    console.print(f"[dim]AI says: {response} (no LLM)[/dim]")
    return response


def get_vote(role: str, choices: list[str], transcript: list[dict]) -> str:
    """Choose who to vote for during the voting phase."""
    if _instance is not None:
        return _instance.get_vote(role, choices, transcript)
    player_choices = [c for c in choices if c != "No one"]
    choice = random.choice(player_choices) if player_choices else "No one"
    console.print(f"[dim]AI votes for: {choice} (no LLM)[/dim]")
    return choice
