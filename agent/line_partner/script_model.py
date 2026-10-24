"""Data model for a parsed script: Script -> Scene -> Line."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Line:
    """A single line of dialogue spoken by one character."""

    character: str
    text: str

    def prompt_hint(self, n_words: int = 4) -> str:
        """The first few words of this line, used to prompt an actor who has gone up."""
        words = self.text.split()
        return " ".join(words[:n_words])


@dataclass(frozen=True)
class Scene:
    """A named, ordered sequence of lines."""

    name: str
    lines: tuple[Line, ...]


@dataclass(frozen=True)
class Script:
    """A full script: metadata plus an ordered sequence of scenes."""

    title: str
    source: str
    scenes: tuple[Scene, ...]

    @property
    def characters(self) -> tuple[str, ...]:
        """All distinct character names, in first-appearance order."""
        seen: list[str] = []
        for scene in self.scenes:
            for line in scene.lines:
                if line.character not in seen:
                    seen.append(line.character)
        return tuple(seen)

    def scene_index(self, name: str) -> int:
        """Index of the scene whose name matches (case-insensitively).

        Raises ValueError if no scene has that name.
        """
        for i, scene in enumerate(self.scenes):
            if scene.name.lower() == name.lower():
                return i
        raise ValueError(f"no scene named {name!r}")

    def all_lines(self) -> tuple[tuple[int, Line], ...]:
        """Every line across all scenes, as (scene_index, line) pairs, in script order."""
        result: list[tuple[int, Line]] = []
        for i, scene in enumerate(self.scenes):
            for line in scene.lines:
                result.append((i, line))
        return tuple(result)
