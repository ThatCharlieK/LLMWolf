"""Night phase: fixed-order role actions with sound and UI."""

import questionary
from rich.console import Console

from werewolf.state import GameState, get_role_team
from werewolf.ui import (
    clear_screen, play_sound, show_panel, show_big_text,
    pause, ROLE_COLORS, wait_for_enter,
)

console = Console()

# Fixed night action order
NIGHT_ORDER = ["Werewolf", "Seer", "Robber", "Troublemaker", "Witch"]

# Sound file mappings
WAKE_SOUNDS = {
    "Werewolf": "werewolves_wake_up.mp3",
    "Seer": "seer_wake_up.mp3",
    "Robber": "robber_wake_up.mp3",
    "Troublemaker": "troublemaker_wake_up.mp3",
    "Witch": "witch_wake_up.mp3",
}

CLOSE_SOUNDS = {
    "Werewolf": "werewolves_close_eyes.mp3",
    "Seer": "seer_close_eyes.mp3",
    "Robber": "robber_close_eyes.mp3",
    "Troublemaker": "troublemaker_close_eyes.mp3",
    "Witch": "witch_close_eyes.mp3",
}

# Role action dispatch
ACTION_FUNCS = {}


def run_night(state: GameState) -> GameState:
    """Run the full night phase, executing each role's action in order.

    Returns the modified game state after all night actions.
    """
    clear_screen()
    show_big_text("NIGHT PHASE", style="bold red")
    play_sound("everyone_close_eyes.mp3")
    pause(3)

    all_roles = list(state.current_roles.values()) + state.center_cards

    for role in NIGHT_ORDER:
        if role not in all_roles:
            continue

        # Find players with this role (from original_roles — night actions are based on dealt role)
        role_players = [p for p in state.players if state.original_roles[p] == role]

        if not role_players:
            # Role exists only in center — skip the action
            continue

        _run_role_action(state, role, role_players)

    clear_screen()
    show_big_text("NIGHT PHASE COMPLETE", style="bold green")
    play_sound("everyone_wake_up.mp3")
    pause(2)

    return state


def _run_role_action(state: GameState, role: str, role_players: list[str]):
    """Execute the night action sequence for a given role.

    Follows the standard pattern: clear → wake sound → action UI → close sound → clear.
    """
    color = ROLE_COLORS.get(role, "white")

    clear_screen()
    play_sound(WAKE_SOUNDS[role])
    pause(2)

    # Run the role-specific action
    if role == "Werewolf":
        _werewolf_action(state, role_players)
    elif role == "Seer":
        _seer_action(state, role_players[0])
    elif role == "Robber":
        _robber_action(state, role_players[0])
    elif role == "Troublemaker":
        _troublemaker_action(state, role_players[0])
    elif role == "Witch":
        _witch_action(state, role_players[0])

    pause(4)
    play_sound(CLOSE_SOUNDS[role])
    clear_screen()
    pause(3)


def _werewolf_action(state: GameState, werewolf_players: list[str]):
    """Werewolf night action.

    Multiple werewolves: see each other. Lone wolf: peek at one center card.
    """
    color = ROLE_COLORS["Werewolf"]

    if len(werewolf_players) >= 2:
        names = ", ".join(werewolf_players)
        show_panel(
            "Werewolves",
            f"The werewolves are: [bold {color}]{names}[/bold {color}]\n\n"
            "Look at each other and remember your allies.",
            style=color,
        )
        state.night_log.append(f"Werewolves ({names}) saw each other.")
        wait_for_enter()
    else:
        player = werewolf_players[0]
        show_panel(
            f"{player} — Lone Werewolf",
            "You are the only werewolf!\n"
            "You may look at one center card.",
            style=color,
        )

        choice = questionary.select(
            "Which center card do you want to look at?",
            choices=["Center card 1", "Center card 2", "Center card 3"],
        ).ask()

        idx = int(choice.split()[-1]) - 1
        card = state.center_cards[idx]
        card_color = ROLE_COLORS.get(card, "white")

        show_panel(
            f"Center Card {idx + 1}",
            f"The card is: [bold {card_color}]{card}[/bold {card_color}]",
            style=color,
        )
        state.night_log.append(
            f"{player} (Lone Werewolf) looked at center card {idx + 1}: {card}."
        )


def _seer_action(state: GameState, player: str):
    """Seer night action.

    Look at one player's card OR two center cards.
    """
    color = ROLE_COLORS["Seer"]

    show_panel(
        f"{player} — Seer",
        "You may look at another player's card,\n"
        "or look at two of the center cards.",
        style=color,
    )

    action = questionary.select(
        "What would you like to do?",
        choices=["Look at a player's card", "Look at two center cards"],
    ).ask()

    if action == "Look at a player's card":
        others = [p for p in state.players if p != player]
        target = questionary.select(
            "Whose card do you want to see?",
            choices=others,
        ).ask()

        role = state.current_roles[target]
        role_color = ROLE_COLORS.get(role, "white")

        show_panel(
            f"{target}'s Card",
            f"{target} is the [bold {role_color}]{role}[/bold {role_color}]",
            style=color,
        )
        state.night_log.append(f"{player} (Seer) looked at {target}'s card: {role}.")

    else:
        # Look at two center cards
        choices = questionary.checkbox(
            "Choose exactly 2 center cards to look at:",
            choices=["Center card 1", "Center card 2", "Center card 3"],
            validate=lambda selected: (
                len(selected) == 2 or "You must select exactly 2 cards"
            ),
        ).ask()

        results = []
        for choice in choices:
            idx = int(choice.split()[-1]) - 1
            card = state.center_cards[idx]
            card_color = ROLE_COLORS.get(card, "white")
            results.append(f"Center card {idx + 1}: [bold {card_color}]{card}[/bold {card_color}]")

        show_panel(
            "Center Cards",
            "\n".join(results),
            style=color,
        )
        indices = [int(c.split()[-1]) - 1 for c in choices]
        cards = [state.center_cards[i] for i in indices]
        state.night_log.append(
            f"{player} (Seer) looked at center cards {indices[0]+1} and {indices[1]+1}: "
            f"{cards[0]} and {cards[1]}."
        )


def _robber_action(state: GameState, player: str):
    """Robber night action.

    Exchange card with another player, then view the new card.
    """
    color = ROLE_COLORS["Robber"]

    show_panel(
        f"{player} — Robber",
        "You must exchange your card with another player's card,\n"
        "then view your new card.",
        style=color,
    )

    others = [p for p in state.players if p != player]
    target = questionary.select(
        "Whose card do you want to steal?",
        choices=others,
    ).ask()

    # Swap cards
    state.current_roles[player], state.current_roles[target] = (
        state.current_roles[target], state.current_roles[player]
    )

    new_role = state.current_roles[player]
    new_color = ROLE_COLORS.get(new_role, "white")

    show_panel(
        "Your New Card",
        f"You swapped with {target}.\n"
        f"Your new role is: [bold {new_color}]{new_role}[/bold {new_color}]",
        style=color,
    )
    state.night_log.append(
        f"{player} (Robber) swapped cards with {target}. "
        f"{player} is now {new_role}. {target} is now Robber."
    )


def _troublemaker_action(state: GameState, player: str):
    """Troublemaker night action.

    Exchange cards between two other players. Does not learn what the cards are.
    """
    color = ROLE_COLORS["Troublemaker"]

    show_panel(
        f"{player} — Troublemaker",
        "You may exchange cards between two other players.\n"
        "You will not see what the cards are.",
        style=color,
    )

    others = [p for p in state.players if p != player]

    first = questionary.select(
        "Choose the first player:",
        choices=others,
    ).ask()

    remaining = [p for p in others if p != first]

    second = questionary.select(
        "Choose the second player:",
        choices=remaining,
    ).ask()

    # Swap the two players' cards
    state.current_roles[first], state.current_roles[second] = (
        state.current_roles[second], state.current_roles[first]
    )

    show_panel(
        "Done",
        f"You swapped {first}'s and {second}'s cards.",
        style=color,
    )
    state.night_log.append(
        f"{player} (Troublemaker) swapped {first}'s and {second}'s cards."
    )


def _witch_action(state: GameState, player: str):
    """Witch night action.

    May look at one center card. If she does, she must swap it with any player's card.
    """
    color = ROLE_COLORS["Witch"]

    show_panel(
        f"{player} — Witch",
        "You may look at one center card.\n"
        "If you do, you must swap it with any player's card (including yours).",
        style=color,
    )

    action = questionary.select(
        "Do you want to look at a center card?",
        choices=["Yes", "No"],
    ).ask()

    if action == "No":
        show_panel("Done", "You chose not to act.", style=color)
        state.night_log.append(f"{player} (Witch) chose not to act.")
        return

    # Pick a center card to look at
    choice = questionary.select(
        "Which center card do you want to look at?",
        choices=["Center card 1", "Center card 2", "Center card 3"],
    ).ask()

    idx = int(choice.split()[-1]) - 1
    card = state.center_cards[idx]
    card_color = ROLE_COLORS.get(card, "white")

    show_panel(
        f"Center Card {idx + 1}",
        f"The card is: [bold {card_color}]{card}[/bold {card_color}]\n\n"
        "You must now swap this card with a player's card.",
        style=color,
    )

    # Must swap with a player (including self)
    target = questionary.select(
        "Whose card do you want to swap this center card with?",
        choices=state.players,
    ).ask()

    # Swap center card with player's card
    state.center_cards[idx], state.current_roles[target] = (
        state.current_roles[target], state.center_cards[idx]
    )

    show_panel(
        "Done",
        f"You swapped center card {idx + 1} with {target}'s card.",
        style=color,
    )
    state.night_log.append(
        f"{player} (Witch) looked at center card {idx + 1} ({card}) "
        f"and swapped it with {target}'s card."
    )
