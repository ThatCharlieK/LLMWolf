"""Game state dataclass and interactive setup logic."""

import random
from copy import deepcopy
from dataclasses import dataclass, field

import questionary
from rich.console import Console
from rich.table import Table

from werewolf.ui import clear_screen, show_panel, show_big_text, ROLE_COLORS

console = Console()

ROLE_TEAM = {
    "Werewolf": "Werewolf",
    "Seer": "Village",
    "Robber": "Village",
    "Troublemaker": "Village",
    "Villager": "Village",
    "Tanner": "Tanner",
    "Witch": "Village",
}

# All available roles and how many copies can exist
AVAILABLE_ROLES = {
    "Werewolf": 2,
    "Seer": 1,
    "Robber": 1,
    "Troublemaker": 1,
    "Villager": 3,
    "Tanner": 1,
    "Witch": 1,
}


@dataclass
class GameState:
    """Single source of truth for all game data.

    original_roles is never mutated after setup. current_roles is mutated by
    night actions (Robber, Troublemaker). night_log is hidden until endgame.
    """
    players: list[str]
    original_roles: dict[str, str]
    current_roles: dict[str, str]
    center_cards: list[str]
    night_log: list[str] = field(default_factory=list)
    discussion_transcript: list[dict] = field(default_factory=list)


def get_role_team(role: str) -> str:
    """Return 'Werewolf' or 'Village' for a given role name."""
    return ROLE_TEAM.get(role, "Village")


def setup_game() -> GameState:
    """Interactive setup flow: player count, names, role selection, deal cards.

    Returns a fully populated GameState ready for the peek phase.
    """
    show_big_text("GAME SETUP", style="bold blue")

    # 1. Player count
    num_players = int(questionary.select(
        "How many players?",
        choices=[str(n) for n in range(3, 7)],
    ).ask())

    # 2. Player names
    players = []
    for i in range(1, num_players + 1):
        while True:
            name = questionary.text(
                f"Player {i} name:",
                validate=lambda text: len(text.strip()) > 0 or "Name cannot be empty",
            ).ask().strip()
            if name in players:
                console.print(f"[red]'{name}' is already taken. Choose a different name.[/red]")
            else:
                players.append(name)
                break

    total_cards = num_players + 3

    # 3. Role selection
    console.print(f"\n[bold]Select exactly {total_cards} role cards[/bold] (= {num_players} players + 3 center)\n")

    # Build choices: expand each role into individual copies
    role_choices = []
    for role, max_count in AVAILABLE_ROLES.items():
        for i in range(1, max_count + 1):
            label = f"{role}" if max_count == 1 else f"{role} #{i}"
            role_choices.append(questionary.Choice(
                title=label,
                value=(role, i),
                checked=False,
            ))

    # Pre-check a sensible default set
    defaults = _get_default_roles(num_players)
    for choice in role_choices:
        role, idx = choice.value
        count_needed = sum(1 for r in defaults if r == role)
        count_so_far = sum(1 for c in role_choices
                          if c.value[0] == role and c.value[1] < idx and c.checked)
        if idx <= count_needed:
            choice.checked = True

    while True:
        selected = questionary.checkbox(
            "Choose roles:",
            choices=role_choices,
        ).ask()

        role_cards = [role for role, _idx in selected]

        if len(role_cards) != total_cards:
            console.print(
                f"[red]You selected {len(role_cards)} cards but need exactly {total_cards}. Try again.[/red]"
            )
            continue
        break

    # 4. Shuffle and deal
    random.shuffle(role_cards)
    dealt_roles = {}
    for i, player in enumerate(players):
        dealt_roles[player] = role_cards[i]
    center = role_cards[num_players:]

    return GameState(
        players=players,
        original_roles=deepcopy(dealt_roles),
        current_roles=dealt_roles,
        center_cards=center,
    )


def _get_default_roles(num_players: int) -> list[str]:
    """Return a sensible default role set for the given player count.

    Always includes 2 Werewolves, 1 Seer, 1 Robber, 1 Troublemaker,
    then fills the rest with Villagers.
    """
    total = num_players + 3
    roles = ["Werewolf", "Werewolf", "Seer", "Robber", "Troublemaker"]
    while len(roles) < total:
        roles.append("Villager")
    return roles[:total]
