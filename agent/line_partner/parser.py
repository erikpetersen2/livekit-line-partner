"""Parses the project's plain-text script format into a Script.

Format::

    TITLE: <title>
    SOURCE: <source attribution>
    NOTE: <optional free-text notes, any number of lines>

    SCENE: <scene name>

    <CHARACTER>: <line text>
    <CHARACTER>: <line text>
    ...

    SCENE: <next scene name>
    ...

Character names are matched case-insensitively and normalized to upper case.
Blank lines are ignored. Metadata lines (TITLE/SOURCE/NOTE) are only recognized
before the first SCENE: line.
"""

from __future__ import annotations

from .script_model import Line, Scene, Script


class ScriptParseError(ValueError):
    """Raised when script text doesn't match the expected format."""


def parse_script(text: str) -> Script:
    title = ""
    source = ""
    scenes: list[Scene] = []
    current_scene_name: str | None = None
    current_lines: list[Line] = []
    seen_scene = False

    def flush_scene() -> None:
        nonlocal current_scene_name, current_lines
        if current_scene_name is not None:
            scenes.append(Scene(name=current_scene_name, lines=tuple(current_lines)))
        current_scene_name = None
        current_lines = []

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        upper = line.upper()

        if upper.startswith("TITLE:"):
            if seen_scene:
                raise ScriptParseError(
                    f"line {lineno}: TITLE must appear before any SCENE"
                )
            title = line.split(":", 1)[1].strip()
            continue

        if upper.startswith("SOURCE:"):
            if seen_scene:
                raise ScriptParseError(
                    f"line {lineno}: SOURCE must appear before any SCENE"
                )
            source = line.split(":", 1)[1].strip()
            continue

        if upper.startswith("NOTE:"):
            continue

        if upper.startswith("SCENE:"):
            flush_scene()
            current_scene_name = line.split(":", 1)[1].strip()
            seen_scene = True
            continue

        if ":" not in line:
            raise ScriptParseError(
                f"line {lineno}: expected 'CHARACTER: text', got {raw_line!r}"
            )

        if current_scene_name is None:
            raise ScriptParseError(
                f"line {lineno}: dialogue line before any SCENE: header"
            )

        character, _, dialogue = line.partition(":")
        character = character.strip().upper()
        dialogue = dialogue.strip()
        if not character or not dialogue:
            raise ScriptParseError(
                f"line {lineno}: malformed dialogue line {raw_line!r}"
            )
        current_lines.append(Line(character=character, text=dialogue))

    flush_scene()

    if not title:
        raise ScriptParseError("script is missing a TITLE: line")
    if not scenes:
        raise ScriptParseError("script contains no scenes")

    return Script(title=title, source=source, scenes=tuple(scenes))


def parse_script_file(path: str) -> Script:
    with open(path, encoding="utf-8") as f:
        return parse_script(f.read())
