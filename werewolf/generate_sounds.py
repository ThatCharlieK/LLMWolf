"""One-off script to generate night phase sound files using Google Text-to-Speech.

Run once during setup: python -m werewolf.generate_sounds
Requires: pip install gtts
"""

from pathlib import Path

SOUNDS_DIR = Path(__file__).resolve().parent.parent / "sounds"

# Mapping of filename to spoken text
SOUND_CLIPS = {
    "everyone_close_eyes.mp3": "Everyone, close your eyes.",
    "werewolves_wake_up.mp3": (
        "Werewolves, wake up and look for other werewolves."
    ),
    "werewolves_close_eyes.mp3": "Werewolves, close your eyes.",
    "seer_wake_up.mp3": (
        "Seer, wake up. You may look at another player's card, "
        "or two of the center cards."
    ),
    "seer_close_eyes.mp3": "Seer, close your eyes.",
    "robber_wake_up.mp3": (
        "Robber, wake up. You may exchange your card with another "
        "player's card, and then view your new card."
    ),
    "robber_close_eyes.mp3": "Robber, close your eyes.",
    "troublemaker_wake_up.mp3": (
        "Troublemaker, wake up. You may exchange cards between "
        "two other players."
    ),
    "troublemaker_close_eyes.mp3": "Troublemaker, close your eyes.",
    "witch_wake_up.mp3": (
        "Witch, wake up. You may look at one center card. "
        "If you do, you must exchange it with any player's card."
    ),
    "witch_close_eyes.mp3": "Witch, close your eyes.",
    "everyone_wake_up.mp3": "Everyone, wake up!",
    "vote.mp3": "Time to vote.",
}


def generate_sounds():
    """Generate all sound files and save them to the sounds/ directory."""
    try:
        from gtts import gTTS
    except ImportError:
        print("Error: gtts is not installed.")
        print("Install it with: pip install -r requirements-dev.txt")
        return

    SOUNDS_DIR.mkdir(exist_ok=True)

    for filename, text in SOUND_CLIPS.items():
        filepath = SOUNDS_DIR / filename
        print(f"Generating {filename}...", end=" ")
        tts = gTTS(text=text, lang="en", slow=False)
        tts.save(str(filepath))
        print("done")

    print(f"\nAll {len(SOUND_CLIPS)} sound files saved to {SOUNDS_DIR}/")


if __name__ == "__main__":
    generate_sounds()
