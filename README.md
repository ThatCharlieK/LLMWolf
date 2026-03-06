# LLMWolf

Recent work has explored LLM performance in social deduction games (SDGs), but almost exclusively in LLM-vs-LLM settings. Perhaps a the more interesting question — whether an LLM can successfully deceive *humans* and understand complex dynamics of live spoken conversation — remains largely untested. LLMWolf provides a testbed for exactly this: a fully playable terminal-based One Night Ultimate Werewolf game where an LLM sits alongside human players as a first-class participant. The system locally records, transcribes, and diarizes the table's conversation in real time, then periodically yields the floor to the LLM, giving it the ability to speak aloud and engage in open debate. If you're confident your social deduction skills generalize beyond other humans, gather some friends and find out.


Terminal-based **One Night Ultimate Werewolf** for 3–6 human players, run from a single laptop by a moderator. **macOS only.**

<p align="center">
<img src="https://raw.githubusercontent.com/ThatCharlieK/READMEAssets/main/VotingScreen.png" width="400"/>
</p>
<p align="center">
<img src="https://raw.githubusercontent.com/ThatCharlieK/READMEAssets/main/DiscussionScreen.png" width="400"/>
</p>

## Tech Stack

- **Python 3.11+**
- **rich** — terminal UI (panels, tables, countdowns)
- **questionary** — arrow-key selection menus
- **macOS `say`** — text-to-speech for night narration and announcements (built-in, no extra deps)
- **whisperx / sounddevice** — optional voice enrollment & STT for day discussion

## First-Time Setup

### 1. Create a virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

This creates an isolated Python environment and installs the core game packages plus audio dependencies (whisperx, sounddevice, etc.). WhisperX will pull in PyTorch automatically — expect the install to take a few minutes and use ~2 GB of disk.

Each new terminal session, activate the environment first:

```bash
source .venv/bin/activate
```

### 2. Set up HuggingFace for voice recognition (optional)

Voice enrollment and speaker diarization (identifying who said what during discussion) require free models hosted on HuggingFace.

**a) Create a free HuggingFace account**

Go to https://huggingface.co/join and sign up.

**b) Accept the model license agreements**

Visit each of these pages and click "Agree and access repository":
- https://huggingface.co/pyannote/speaker-diarization-3.1
- https://huggingface.co/pyannote/segmentation-3.0
- https://huggingface.co/pyannote/embedding
- https://huggingface.co/pyannote/speaker-diarization-community-1

You must be logged in to HuggingFace when accepting.

**c) Create an access token**

Go to https://huggingface.co/settings/tokens, click "New token", name it anything (e.g. "llmwolf"), and select "Read" access. Copy the token.

**d) Set the token in the `.env` file**

Create (or edit) `werewolf/.env` and add:

```bash
export HF_TOKEN="hf_your_token_here"
```

This file is sourced automatically when you run the game (see step 3). It's already in `.gitignore` so your token won't be committed.

The first time you run the game with voice features enabled, the models will be downloaded (~500 MB total). After that, they're cached locally and no internet connection is needed.

### 3. Run the game

```bash
source werewolf/.env && python -m werewolf.main
```

On first launch, the game will:
1. Ask for player count and names
2. Offer voice enrollment (requires HF_TOKEN — say "No" to skip if not set up)
3. Proceed through peek → night → day → vote phases

## Game Loop

`main.py` orchestrates the full flow:

1. **Title Screen** — welcome splash
2. **Setup** (`state.py`) — player count, names, role selection, shuffle & deal
3. **Voice Enrollment** (optional) — players record samples for speaker ID
4. **Peek Phase** — each player privately views their dealt role
5. **Night Phase** (`night.py`) — roles act in fixed order: Werewolf → Seer → Robber → Troublemaker → Witch
6. **Day Phase** (`day.py`) — timed discussion (5 min default)
7. **Vote Phase** (`vote.py`) — simultaneous vote, tally, win condition check, full reveal

`GameState` (dataclass) is the single source of truth passed through every phase. `original_roles` is immutable; `current_roles` is mutated by night swaps.

## Roles

Werewolf, Seer, Robber, Troublemaker, Villager, Tanner, Witch.
