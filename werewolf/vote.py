"""Voting phase: collect votes, tally, determine winner, reveal endgame."""

from collections import Counter

import questionary
from rich.console import Console
from rich.table import Table

from werewolf.state import GameState, get_role_team
from werewolf.llm import is_ai_player, get_vote
from werewolf.ui import (
    clear_screen, show_panel, show_big_text,
    pause, ROLE_COLORS, wait_for_enter, speak,
)

console = Console()


def run_vote(state: GameState) -> dict:
    """Handle the full voting phase: collect votes, tally, resolve, and reveal.

    Displays the endgame results including roles, night log, and winner.
    Returns a dict with 'votes' and 'winner' keys for logging.
    """
    clear_screen()
    show_big_text("VOTING PHASE", style="bold magenta")
    speak("Time to vote.")

    show_panel(
        "Vote",
        "Each player will vote for who to eliminate.\n"
        "You may also vote for 'No one'.",
        style="magenta",
    )
    wait_for_enter("Press Enter to begin voting...")

    # Collect votes
    votes = {}
    for player in state.players:
        choices = [p for p in state.players if p != player] + ["No one"]

        if is_ai_player(player):
            ai_role = state.original_roles.get(player, "Unknown")
            vote = get_vote(ai_role, choices, state.discussion_transcript)
        else:
            clear_screen()
            show_panel(
                f"{player}'s Vote",
                f"[bold]{player}[/bold], who do you vote to eliminate?",
                style="magenta",
            )
            vote = questionary.select(
                "Your vote:",
                choices=choices,
            ).ask()
            clear_screen()

        votes[player] = vote

    # Tally and resolve
    winner = _resolve_votes(state, votes)
    return {"votes": votes, "winner": winner}


def _resolve_votes(state: GameState, votes: dict[str, str]) -> str:
    """Tally votes, determine elimination, and display endgame results. Returns winner."""
    clear_screen()
    show_big_text("RESULTS", style="bold white")

    # Show how everyone voted
    vote_table = Table(title="Votes", show_header=True, header_style="bold")
    vote_table.add_column("Player", style="bold")
    vote_table.add_column("Voted For")
    for player, vote in votes.items():
        vote_table.add_row(player, vote)
    console.print(vote_table)
    console.print()

    # Tally (exclude "No one" votes from elimination counting)
    tally = Counter(v for v in votes.values() if v != "No one")

    # Determine who is eliminated
    eliminated = []
    if tally:
        max_votes = max(tally.values())
        if max_votes > 1:
            eliminated = [p for p, count in tally.items() if count == max_votes]

    # Announce elimination
    if not eliminated:
        show_panel(
            "No Elimination",
            "No player received more than 1 vote.\nNo one is eliminated!",
            style="yellow",
        )
    else:
        for player in eliminated:
            role = state.current_roles[player]
            role_color = ROLE_COLORS.get(role, "white")
            show_panel(
                "Eliminated!",
                f"[bold]{player}[/bold] was eliminated with {tally[player]} votes.\n"
                f"Their card is: [bold {role_color}]{role}[/bold {role_color}]",
                style="red",
            )

    console.print()

    # Determine winner
    winner = _determine_winner(state, eliminated)

    if winner == "Tanner":
        tanner_color = ROLE_COLORS.get("Tanner", "dark_orange")
        show_big_text("TANNER WINS!", style=f"bold {tanner_color}")
        console.print("[bold]Everyone else loses![/bold]", justify="center")
    else:
        winner_style = "green" if winner == "Village" else "red"
        show_big_text(f"{winner.upper()} TEAM WINS!", style=f"bold {winner_style}")
        # Show "Tanner loses" if a player holds the Tanner role
        tanner_in_game = any(r == "Tanner" for r in state.current_roles.values())
        if tanner_in_game:
            tanner_color = ROLE_COLORS.get("Tanner", "dark_orange")
            console.print(
                f"[bold {tanner_color}]Tanner loses![/bold {tanner_color}]",
                justify="center",
            )
    console.print()

    # Full role reveal table
    _show_role_reveal(state)

    # Center cards
    center_str = "  ".join(
        f"[bold {ROLE_COLORS.get(c, 'white')}]{c}[/bold {ROLE_COLORS.get(c, 'white')}]"
        for c in state.center_cards
    )
    show_panel("Center Cards", center_str, style="blue")
    console.print()

    # Night log
    if state.night_log:
        log_text = "\n".join(f"  {entry}" for entry in state.night_log)
        show_panel("Night Log", log_text, style="dim")

    return winner


def _determine_winner(state: GameState, eliminated: list[str]) -> str:
    """Determine which team wins based on eliminations and role positions.

    Returns 'Tanner', 'Village', or 'Werewolf'. Tanner wins take priority:
    if the Tanner is eliminated, Tanner wins and everyone else loses.
    """
    # Tanner win check — if any eliminated player is the Tanner, Tanner wins
    for player in eliminated:
        if state.current_roles[player] == "Tanner":
            return "Tanner"

    # Standard Village vs Werewolf logic
    player_roles = list(state.current_roles.values())
    werewolves_among_players = any(r == "Werewolf" for r in player_roles)

    if not werewolves_among_players:
        # All werewolf cards are in the center
        # Village wins only if no one was eliminated
        return "Village" if not eliminated else "Werewolf"

    # Check if any eliminated player is a werewolf
    for player in eliminated:
        if state.current_roles[player] == "Werewolf":
            return "Village"

    return "Werewolf"


def _show_role_reveal(state: GameState):
    """Display the full role reveal table showing original and final roles."""
    table = Table(title="Role Reveal", show_header=True, header_style="bold")
    table.add_column("Player", style="bold")
    table.add_column("Original Role")
    table.add_column("Final Role")

    for player in state.players:
        orig = state.original_roles[player]
        final = state.current_roles[player]
        orig_color = ROLE_COLORS.get(orig, "white")
        final_color = ROLE_COLORS.get(final, "white")
        table.add_row(
            player,
            f"[{orig_color}]{orig}[/{orig_color}]",
            f"[{final_color}]{final}[/{final_color}]",
        )

    console.print(table)
    console.print()
