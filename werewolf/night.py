"""Night phase: fixed-order role actions with sound and UI."""

import questionary
from rich.console import Console

from werewolf.state import GameState, get_role_team
from werewolf.llm import is_ai_player, get_night_action, get_checkbox_action
from werewolf.ui import (
    clear_screen, show_panel, show_big_text,
    pause, ROLE_COLORS, wait_for_enter, speak,
)

console = Console()

# Fixed night action order
NIGHT_ORDER = ["Werewolf", "Seer", "Robber", "Troublemaker", "Witch"]

# Spoken lines for each role's wake/close phase
WAKE_LINES = {
    "Werewolf": "Werewolves, wake up and look for other werewolves.",
    "Seer": "Seer, wake up. You may look at another player's card, or two of the center cards.",
    "Robber": "Robber, wake up. You may exchange your card with another player's card, and then view your new card.",
    "Troublemaker": "Troublemaker, wake up. You may exchange cards between two other players.",
    "Witch": "Witch, wake up. You may look at one center card. If you do, you must exchange it with any player's card.",
}

CLOSE_LINES = {
    "Werewolf": "Werewolves, close your eyes.",
    "Seer": "Seer, close your eyes.",
    "Robber": "Robber, close your eyes.",
    "Troublemaker": "Troublemaker, close your eyes.",
    "Witch": "Witch, close your eyes.",
}

# Role action dispatch
ACTION_FUNCS = {}


def run_night(state: GameState) -> GameState:
    """Run the full night phase, executing each role's action in order.

    Returns the modified game state after all night actions.
    """
    clear_screen()
    show_big_text("NIGHT PHASE", style="bold red")
    speak("Everyone, close your eyes.")
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
    speak("Everyone, wake up!")
    pause(2)

    return state


def _run_role_action(state: GameState, role: str, role_players: list[str]):
    """Execute the night action sequence for a given role.

    Follows the standard pattern: clear → wake sound → action UI → close sound → clear.
    """
    color = ROLE_COLORS.get(role, "white")

    clear_screen()
    speak(WAKE_LINES[role])
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
    speak(CLOSE_LINES[role])
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
        if not any(is_ai_player(p) for p in werewolf_players):
            wait_for_enter()
    else:
        player = werewolf_players[0]
        center_choices = ["Center card 1", "Center card 2", "Center card 3"]

        if is_ai_player(player):
            context = "You are the lone werewolf. Pick a center card to peek at."
            choice = get_night_action("Werewolf", "Which center card?", center_choices, context)
        else:
            show_panel(
                f"{player} — Lone Werewolf",
                "You are the only werewolf!\n"
                "You may look at one center card.",
                style=color,
            )
            choice = questionary.select(
                "Which center card do you want to look at?",
                choices=center_choices,
            ).ask()

        idx = int(choice.split()[-1]) - 1
        card = state.center_cards[idx]
        card_color = ROLE_COLORS.get(card, "white")

        if not is_ai_player(player):
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

    action_choices = ["Look at a player's card", "Look at two center cards"]
    others = [p for p in state.players if p != player]

    if is_ai_player(player):
        context = "You are the Seer. You can look at one player's card or two center cards."
        action = get_night_action("Seer", "What would you like to do?", action_choices, context)
    else:
        show_panel(
            f"{player} — Seer",
            "You may look at another player's card,\n"
            "or look at two of the center cards.",
            style=color,
        )
        action = questionary.select(
            "What would you like to do?",
            choices=action_choices,
        ).ask()

    if action == "Look at a player's card":
        if is_ai_player(player):
            context = "You are the Seer. Choose a player's card to look at."
            target = get_night_action("Seer", "Whose card do you want to see?", others, context)
        else:
            target = questionary.select(
                "Whose card do you want to see?",
                choices=others,
            ).ask()

        role = state.current_roles[target]
        role_color = ROLE_COLORS.get(role, "white")

        if not is_ai_player(player):
            show_panel(
                f"{target}'s Card",
                f"{target} is the [bold {role_color}]{role}[/bold {role_color}]",
                style=color,
            )
        state.night_log.append(f"{player} (Seer) looked at {target}'s card: {role}.")

    else:
        # Look at two center cards
        center_options = ["Center card 1", "Center card 2", "Center card 3"]
        if is_ai_player(player):
            context = "You are the Seer. Choose exactly 2 center cards to look at."
            chosen = get_checkbox_action("Seer", "Choose 2 center cards:", center_options, 2, context)
        else:
            chosen = questionary.checkbox(
                "Choose exactly 2 center cards to look at:",
                choices=center_options,
                validate=lambda selected: (
                    len(selected) == 2 or "You must select exactly 2 cards"
                ),
            ).ask()

        results = []
        for choice in chosen:
            idx = int(choice.split()[-1]) - 1
            card = state.center_cards[idx]
            card_color = ROLE_COLORS.get(card, "white")
            results.append(f"Center card {idx + 1}: [bold {card_color}]{card}[/bold {card_color}]")

        if not is_ai_player(player):
            show_panel(
                "Center Cards",
                "\n".join(results),
                style=color,
            )
        indices = [int(c.split()[-1]) - 1 for c in chosen]
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

    others = [p for p in state.players if p != player]

    if is_ai_player(player):
        context = "You are the Robber. Choose a player to swap cards with."
        target = get_night_action("Robber", "Whose card do you want to steal?", others, context)
    else:
        show_panel(
            f"{player} — Robber",
            "You must exchange your card with another player's card,\n"
            "then view your new card.",
            style=color,
        )
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

    if not is_ai_player(player):
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

    others = [p for p in state.players if p != player]

    if is_ai_player(player):
        context = "You are the Troublemaker. Choose two other players to swap cards between."
        first = get_night_action("Troublemaker", "Choose the first player:", others, context)
        remaining = [p for p in others if p != first]
        second = get_night_action("Troublemaker", "Choose the second player:", remaining, context)
    else:
        show_panel(
            f"{player} — Troublemaker",
            "You may exchange cards between two other players.\n"
            "You will not see what the cards are.",
            style=color,
        )
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

    if not is_ai_player(player):
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

    center_choices = ["Center card 1", "Center card 2", "Center card 3"]

    if is_ai_player(player):
        context = "You are the Witch. You may look at one center card. If you do, you must swap it with any player's card."
        action = get_night_action("Witch", "Do you want to look at a center card?", ["Yes", "No"], context)
    else:
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
        if not is_ai_player(player):
            show_panel("Done", "You chose not to act.", style=color)
        state.night_log.append(f"{player} (Witch) chose not to act.")
        return

    # Pick a center card to look at
    if is_ai_player(player):
        choice = get_night_action("Witch", "Which center card?", center_choices, context)
    else:
        choice = questionary.select(
            "Which center card do you want to look at?",
            choices=center_choices,
        ).ask()

    idx = int(choice.split()[-1]) - 1
    card = state.center_cards[idx]
    card_color = ROLE_COLORS.get(card, "white")

    if not is_ai_player(player):
        show_panel(
            f"Center Card {idx + 1}",
            f"The card is: [bold {card_color}]{card}[/bold {card_color}]\n\n"
            "You must now swap this card with a player's card.",
            style=color,
        )

    # Must swap with a player (including self)
    if is_ai_player(player):
        context += f" The center card is {card}. Choose a player to swap it with."
        target = get_night_action("Witch", "Swap with which player?", state.players, context)
    else:
        target = questionary.select(
            "Whose card do you want to swap this center card with?",
            choices=state.players,
        ).ask()

    # Swap center card with player's card
    state.center_cards[idx], state.current_roles[target] = (
        state.current_roles[target], state.center_cards[idx]
    )

    if not is_ai_player(player):
        show_panel(
            "Done",
            f"You swapped center card {idx + 1} with {target}'s card.",
            style=color,
        )
    state.night_log.append(
        f"{player} (Witch) looked at center card {idx + 1} ({card}) "
        f"and swapped it with {target}'s card."
    )
