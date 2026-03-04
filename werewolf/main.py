"""Entry point for One Night Ultimate Werewolf CLI game."""

import questionary
from rich.console import Console

from werewolf.state import GameState, setup_game
from werewolf.night import run_night
from werewolf.day import run_day
from werewolf.vote import run_vote
from werewolf.ui import (
    clear_screen, init_sound, init_tts_ui, show_panel, show_big_text,
    pause, ROLE_COLORS, wait_for_enter,
)

console = Console()


def show_title_screen():
    """Display the game title screen."""
    clear_screen()
    console.print()
    console.print()
    show_big_text("ONE NIGHT", style="bold red")
    show_big_text("ULTIMATE WEREWOLF", style="bold red")
    console.print()
    show_panel(
        "Welcome",
        "A game of deception for 3-6 players.\n"
        "One laptop, one night, one vote.",
        style="red",
    )
    wait_for_enter("Press Enter to start...")


def run_peek_phase(state: GameState):
    """Let each player privately peek at their dealt role card.

    Players take turns looking at the laptop to see their role.
    """
    clear_screen()
    show_big_text("PEEK PHASE", style="bold blue")
    show_panel(
        "Peek at Your Card",
        "Each player will take a turn looking at their role card.\n"
        "Don't let anyone else see!",
        style="blue",
    )
    wait_for_enter()

    for player in state.players:
        clear_screen()
        show_panel(
            "Pass the Laptop",
            f"[bold]{player}[/bold], it's your turn to peek.\n"
            "Make sure no one else is looking!",
            style="blue",
        )
        wait_for_enter(f"{player}, press Enter when ready...")

        role = state.original_roles[player]
        color = ROLE_COLORS.get(role, "white")
        clear_screen()
        show_panel(
            f"{player}'s Role",
            f"You are the [bold {color}]{role}[/bold {color}]",
            style=color,
        )
        wait_for_enter("Press Enter when you've memorized your role...")
        clear_screen()

    show_panel(
        "All Players Have Peeked",
        "Everyone, put your cards face down and remember your role.\n"
        "The night phase is about to begin.",
        style="blue",
    )
    wait_for_enter()


def run_enrollment(players: list[str]) -> dict:
    """Run voice enrollment for speaker diarization.

    Each player records a short voice sample so the system can identify
    who is speaking during the day discussion phase.
    """
    try:
        from werewolf.stt import init_stt, enroll_speakers
    except ImportError:
        console.print("[dim]STT not available — skipping voice enrollment.[/dim]")
        return {}

    clear_screen()
    show_big_text("VOICE ENROLLMENT", style="bold blue")
    show_panel(
        "Voice Setup",
        "Each player will record a short voice sample.\n"
        "This helps the system identify who is speaking during discussion.",
        style="blue",
    )

    confirm = questionary.confirm(
        "Enable voice recording for this game?", default=True
    ).ask()
    if not confirm:
        return {}

    init_stt()
    enrollments = enroll_speakers(players)

    if enrollments:
        console.print(
            f"\n[green]Enrolled {len(enrollments)}/{len(players)} players.[/green]"
        )
    wait_for_enter()
    return enrollments


def main():
    """Run the full game loop: title → setup → peek → night → day → vote → replay."""
    init_sound()
    init_tts_ui()

    while True:
        show_title_screen()
        state = setup_game()
        enrollments = run_enrollment(state.players)
        run_peek_phase(state)
        state = run_night(state)
        run_day(state, enrollments=enrollments)
        run_vote(state)

        console.print()
        play_again = questionary.confirm("Play again?", default=True).ask()
        if not play_again:
            clear_screen()
            show_big_text("Thanks for playing!", style="bold green")
            console.print()
            break


if __name__ == "__main__":
    main()
