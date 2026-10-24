"""The cue / listen / prompt state machine that drives a Line Partner session.

Deliberately has no knowledge of LiveKit, STT, TTS, or the LLM. It consumes a
parsed `Script` and an actor's chosen character, and produces a sequence of
`Say` / `Listen` / `Done` actions for a caller (the agent pipeline) to act on.
Command *interpretation* - turning free-form speech into one of "line?", "from
the top", "skip to scene N", "again" - is the LLM's job elsewhere in the
pipeline; this module only takes already-classified commands, so it stays
fully deterministic and testable without any LLM involved.
"""

from __future__ import annotations

from dataclasses import dataclass

from .matcher import DEFAULT_MATCH_THRESHOLD, is_line_match
from .script_model import Line, Script


@dataclass(frozen=True)
class Say:
    """Instruction: speak this line verbatim (a non-actor cue line)."""

    character: str
    text: str


@dataclass(frozen=True)
class Listen:
    """Instruction: it's the actor's turn - wait for their spoken line."""

    character: str
    expected_text: str


@dataclass(frozen=True)
class Done:
    """Instruction: there are no more lines (end of script)."""


Action = Say | Listen | Done


class LinePartnerSession:
    """Tracks progress through a `Script` for one actor playing one character."""

    def __init__(self, script: Script, actor_character: str) -> None:
        actor_character = actor_character.strip().upper()
        if actor_character not in script.characters:
            raise ValueError(
                f"{actor_character!r} is not a character in this script "
                f"(available: {', '.join(script.characters)})"
            )
        self.script = script
        self.actor_character = actor_character
        self._flat: tuple[tuple[int, Line], ...] = script.all_lines()
        self._pos = 0
        self._last_npc_line: Line | None = None

    def start(self) -> list[Action]:
        """Call once to get the first batch of actions (from the top of the script)."""
        return self._advance()

    def current_expected_line(self) -> Line | None:
        """The line the actor is currently expected to say, or None if not their turn / done."""
        if self._pos >= len(self._flat):
            return None
        _, line = self._flat[self._pos]
        return line if line.character == self.actor_character else None

    def submit_line(
        self, spoken_text: str, threshold: float = DEFAULT_MATCH_THRESHOLD
    ) -> tuple[bool, list[Action]]:
        """Submit the actor's spoken line for the current cue.

        Returns (matched, actions). If matched, `actions` is the next batch
        (subsequent NPC lines, then the next Listen or Done). If not matched,
        `actions` is empty and state is unchanged - the caller just keeps
        listening (no automatic "you got it wrong" behavior; the actor asks
        for help explicitly via the "line?" command instead).
        """
        expected = self.current_expected_line()
        if expected is None:
            raise RuntimeError("no line is currently expected from the actor")

        if not is_line_match(spoken_text, expected.text, threshold=threshold):
            return False, []

        self._pos += 1
        return True, self._advance()

    def line_hint(self, n_words: int = 4) -> str:
        """The first few words of the currently expected line, for the "line?" command."""
        expected = self.current_expected_line()
        if expected is None:
            raise RuntimeError("no line is currently expected from the actor")
        return expected.prompt_hint(n_words=n_words)

    def again(self) -> Say | None:
        """Re-deliver the most recently spoken NPC line, for the "again" command."""
        if self._last_npc_line is None:
            return None
        return Say(
            character=self._last_npc_line.character, text=self._last_npc_line.text
        )

    def from_the_top(self) -> list[Action]:
        """Restart the current scene, for the "from the top" command."""
        current_scene_idx = self._current_scene_index()
        self._pos = self._scene_start_index(current_scene_idx)
        self._last_npc_line = None
        return self._advance()

    def skip_to_scene(self, scene_number: int) -> list[Action]:
        """Jump to the start of a scene (1-indexed), for the "skip to scene N" command."""
        scene_idx = scene_number - 1
        if not 0 <= scene_idx < len(self.script.scenes):
            raise ValueError(
                f"scene {scene_number} does not exist "
                f"(script has {len(self.script.scenes)} scene(s))"
            )
        self._pos = self._scene_start_index(scene_idx)
        self._last_npc_line = None
        return self._advance()

    def _advance(self) -> list[Action]:
        """Emit Say actions for consecutive non-actor lines, stopping at Listen or Done."""
        actions: list[Action] = []
        while self._pos < len(self._flat):
            _, line = self._flat[self._pos]
            if line.character == self.actor_character:
                actions.append(
                    Listen(character=line.character, expected_text=line.text)
                )
                return actions
            actions.append(Say(character=line.character, text=line.text))
            self._last_npc_line = line
            self._pos += 1
        actions.append(Done())
        return actions

    def _current_scene_index(self) -> int:
        if self._pos < len(self._flat):
            return self._flat[self._pos][0]
        # Past the end: treat as still "in" the last scene for `from the top`.
        return len(self.script.scenes) - 1

    def _scene_start_index(self, scene_idx: int) -> int:
        for i, (s_idx, _) in enumerate(self._flat):
            if s_idx == scene_idx:
                return i
        return len(self._flat)
