"""Claude (Anthropic) implementation of the LLM interface.

Maintains a persistent conversation history across the entire game so
Claude has full context of night actions, day discussion, and its own
prior statements. Prompts are loaded from prompts.json.
"""

import json
import os
import random

from rich.console import Console

from werewolf.llm import LLM

console = Console()


class ClaudeLLM(LLM):
    """Anthropic Claude provider for AI player interaction."""

    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        self._model = model
        self._client = None
        self._conversation: list[dict] = []
        self._system_prompt: str = ""
        self._speaking_prompt: str = ""
        self._initialized: bool = False

        self._init()

    def _init(self) -> None:
        """Initialize the Anthropic client and load prompts."""
        try:
            import anthropic
        except ImportError:
            console.print("[yellow]anthropic package not installed — AI will use dummy responses[/yellow]")
            return

        try:
            env = self._load_env()
            api_key = env.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                console.print("[yellow]ANTHROPIC_API_KEY not found — AI will use dummy responses[/yellow]")
                return

            self._client = anthropic.Anthropic(api_key=api_key)

            prompts_path = os.path.join(os.path.dirname(__file__), "prompts.json")
            with open(prompts_path) as f:
                prompts = json.load(f)
            self._system_prompt = prompts["pre_prompt"]
            self._speaking_prompt = prompts["speaking_prompt"]

            self._initialized = True
            console.print("[dim]LLM initialized successfully (Claude)[/dim]")
        except Exception as e:
            console.print(f"[yellow]LLM init failed: {e} — AI will use dummy responses[/yellow]")

    @staticmethod
    def _load_env() -> dict[str, str]:
        """Parse the .env file, handling the `export VAR="val"` format."""
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if not os.path.exists(env_path):
            return {}
        env = {}
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:]
                if "=" in line:
                    key, val = line.split("=", 1)
                    env[key.strip()] = val.strip().strip('"').strip("'")
        return env

    def _call_api(self, use_thinking: bool = False, thinking_budget: int = 10000) -> str | None:
        """Make an API call with the current conversation history."""
        if not self._initialized or self._client is None:
            return None

        try:
            kwargs = {
                "model": self._model,
                "max_tokens": 16000 if use_thinking else 1024,
                "system": self._system_prompt,
                "messages": self._conversation,
            }

            if use_thinking:
                kwargs["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": thinking_budget,
                }

            response = self._client.messages.create(**kwargs)

            text_parts = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)

            return "\n".join(text_parts).strip() if text_parts else None
        except Exception as e:
            console.print(f"[dim]LLM API error: {e}[/dim]")
            return None

    @staticmethod
    def _match_choice(response: str, choices: list[str]) -> str | None:
        """Try to match a response to one of the valid choices."""
        response_stripped = response.strip()

        for choice in choices:
            if response_stripped == choice:
                return choice

        for choice in choices:
            if choice.lower() in response_stripped.lower():
                return choice

        return None

    def reset_conversation(self) -> None:
        self._conversation = []

    def notify_role(self, role: str, players: list[str]) -> None:
        if not self._initialized:
            return

        player_list = ", ".join(players)
        self._conversation.append({
            "role": "user",
            "content": (
                f"The game is starting. The players are: {player_list}. "
                f"You have been dealt the role: {role}. "
                f"Remember your role — it determines your team and your night action. "
                f"The night phase is about to begin."
            ),
        })
        self._conversation.append({
            "role": "assistant",
            "content": "Understood. I know my role and I'm ready for the night phase.",
        })

    def notify_night_result(self, message: str) -> None:
        if not self._initialized:
            return

        self._conversation.append({"role": "user", "content": message})
        self._conversation.append({
            "role": "assistant",
            "content": "Got it. I'll remember this information.",
        })

    def get_night_action(self, role: str, prompt: str, choices: list[str], context: str) -> str:
        if not self._initialized:
            choice = random.choice(choices)
            console.print(f"[dim]AI ({role}) chose: {choice} (fallback)[/dim]")
            return choice

        choices_text = "\n".join(f"- {c}" for c in choices)
        self._conversation.append({
            "role": "user",
            "content": (
                f"{context}\n\n"
                f"{prompt}\n\n"
                f"Your options:\n{choices_text}\n\n"
                f"Respond with ONLY the exact text of your chosen option."
            ),
        })

        response = self._call_api(use_thinking=False)

        if response:
            matched = self._match_choice(response, choices)
            if matched:
                self._conversation.append({"role": "assistant", "content": matched})
                console.print(f"[dim]AI ({role}) chose: {matched}[/dim]")
                return matched
            console.print(f"[dim]AI response didn't match choices: {response!r}[/dim]")

        self._conversation.pop()
        choice = random.choice(choices)
        self._conversation.append({
            "role": "user",
            "content": f"{context}\n\n{prompt}",
        })
        self._conversation.append({"role": "assistant", "content": choice})
        console.print(f"[dim]AI ({role}) chose: {choice} (fallback)[/dim]")
        return choice

    def get_checkbox_action(
        self, role: str, prompt: str, choices: list[str], count: int, context: str
    ) -> list[str]:
        if not self._initialized:
            selected = choices[:count]
            console.print(f"[dim]AI ({role}) chose: {selected} (fallback)[/dim]")
            return selected

        choices_text = "\n".join(f"- {c}" for c in choices)
        self._conversation.append({
            "role": "user",
            "content": (
                f"{context}\n\n"
                f"{prompt}\n\n"
                f"Your options:\n{choices_text}\n\n"
                f"Choose exactly {count}. Respond with ONLY the exact option texts, one per line."
            ),
        })

        response = self._call_api(use_thinking=False)

        if response:
            selected = []
            for line in response.strip().split("\n"):
                matched = self._match_choice(line.strip(), choices)
                if matched and matched not in selected:
                    selected.append(matched)
            if len(selected) == count:
                self._conversation.append({"role": "assistant", "content": response})
                console.print(f"[dim]AI ({role}) chose: {selected}[/dim]")
                return selected
            console.print(f"[dim]AI checkbox response parse failed: {response!r}[/dim]")

        self._conversation.pop()
        selected = choices[:count]
        self._conversation.append({
            "role": "user",
            "content": f"{context}\n\n{prompt}",
        })
        self._conversation.append({"role": "assistant", "content": "\n".join(selected)})
        console.print(f"[dim]AI ({role}) chose: {selected} (fallback)[/dim]")
        return selected

    def get_day_response(self, role: str, transcript: list[dict]) -> str:
        if not self._initialized:
            idx = len(transcript) % 5
            fallback = [
                "Hmm, I'm not sure who the werewolf is, but something feels off.",
                "I think we should look more carefully at who's being too quiet.",
                "I have a feeling someone here isn't telling the truth.",
                "Let's think about this logically. Who has the most to gain from lying?",
                "I'm suspicious, but I want to hear what everyone else thinks first.",
            ]
            response = fallback[idx]
            console.print(f"[dim]AI says: {response} (fallback)[/dim]")
            return response

        if transcript:
            transcript_text = "\n".join(
                f"{entry['speaker']}: {entry['text']}" for entry in transcript
            )
            transcript_section = f"Discussion so far:\n{transcript_text}\n\n"
        else:
            transcript_section = "No one has spoken yet.\n\n"

        self._conversation.append({
            "role": "user",
            "content": f"{transcript_section}{self._speaking_prompt}",
        })

        response = self._call_api(use_thinking=True, thinking_budget=10000)

        if response:
            cleaned = response.strip().strip('"').strip("'")
            self._conversation.append({"role": "assistant", "content": cleaned})
            console.print(f"[dim]AI says: {cleaned}[/dim]")
            return cleaned

        self._conversation.pop()
        idx = len(transcript) % 5
        fallback = "I'm suspicious, but I want to hear what everyone else thinks first."
        console.print(f"[dim]AI says: {fallback} (fallback)[/dim]")
        return fallback

    def get_vote(self, role: str, choices: list[str], transcript: list[dict]) -> str:
        if not self._initialized:
            player_choices = [c for c in choices if c != "No one"]
            choice = random.choice(player_choices) if player_choices else "No one"
            console.print(f"[dim]AI votes for: {choice} (fallback)[/dim]")
            return choice

        if transcript:
            transcript_text = "\n".join(
                f"{entry['speaker']}: {entry['text']}" for entry in transcript
            )
            transcript_section = f"Full discussion transcript:\n{transcript_text}\n\n"
        else:
            transcript_section = "There was no discussion.\n\n"

        choices_text = "\n".join(f"- {c}" for c in choices)
        self._conversation.append({
            "role": "user",
            "content": (
                f"The discussion is over. It's time to vote.\n\n"
                f"{transcript_section}"
                f"Who do you vote to eliminate?\n\n"
                f"Your options:\n{choices_text}\n\n"
                f"Respond with ONLY the exact name of the player you vote for, or \"No one\"."
            ),
        })

        response = self._call_api(use_thinking=True, thinking_budget=5000)

        if response:
            matched = self._match_choice(response, choices)
            if matched:
                self._conversation.append({"role": "assistant", "content": matched})
                console.print(f"[dim]AI votes for: {matched}[/dim]")
                return matched
            console.print(f"[dim]AI vote response didn't match: {response!r}[/dim]")

        self._conversation.pop()
        player_choices = [c for c in choices if c != "No one"]
        choice = random.choice(player_choices) if player_choices else "No one"
        self._conversation.append({
            "role": "user",
            "content": "Who do you vote to eliminate?",
        })
        self._conversation.append({"role": "assistant", "content": choice})
        console.print(f"[dim]AI votes for: {choice} (fallback)[/dim]")
        return choice
