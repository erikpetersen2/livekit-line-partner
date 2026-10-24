import pathlib

import pytest

from line_partner.parser import ScriptParseError, parse_script

SAMPLE = """\
TITLE: Sample Play
SOURCE: Test fixture

SCENE: Scene One

ALICE: Hello there.
BOB: Hello yourself.

SCENE: Scene Two

ALICE: We meet again.
BOB: Indeed we do.
ALICE: The end.
"""


def test_parses_title_and_source():
    script = parse_script(SAMPLE)
    assert script.title == "Sample Play"
    assert script.source == "Test fixture"


def test_parses_scenes_in_order():
    script = parse_script(SAMPLE)
    assert [s.name for s in script.scenes] == ["Scene One", "Scene Two"]


def test_parses_lines_within_scene():
    script = parse_script(SAMPLE)
    scene_one = script.scenes[0]
    assert [(line.character, line.text) for line in scene_one.lines] == [
        ("ALICE", "Hello there."),
        ("BOB", "Hello yourself."),
    ]


def test_characters_in_first_appearance_order():
    script = parse_script(SAMPLE)
    assert script.characters == ("ALICE", "BOB")


def test_character_names_normalized_to_upper():
    text = "TITLE: T\nSOURCE: S\n\nSCENE: One\n\nalice: hi\n"
    script = parse_script(text)
    assert script.scenes[0].lines[0].character == "ALICE"


def test_missing_title_raises():
    with pytest.raises(ScriptParseError, match="TITLE"):
        parse_script("SOURCE: S\n\nSCENE: One\n\nALICE: hi\n")


def test_no_scenes_raises():
    with pytest.raises(ScriptParseError, match="no scenes"):
        parse_script("TITLE: T\nSOURCE: S\n")


def test_dialogue_before_scene_raises():
    with pytest.raises(ScriptParseError, match="before any SCENE"):
        parse_script("TITLE: T\nSOURCE: S\n\nALICE: too early\n")


def test_malformed_line_without_colon_raises():
    with pytest.raises(ScriptParseError, match="expected"):
        parse_script("TITLE: T\nSOURCE: S\n\nSCENE: One\n\nthis has no colon\n")


def test_all_lines_tracks_scene_index():
    script = parse_script(SAMPLE)
    all_lines = script.all_lines()
    assert all_lines[0][0] == 0
    assert all_lines[2][0] == 1  # "We meet again." is the first line of scene 2
    assert all_lines[2][1].text == "We meet again."


def test_real_script_file_parses():
    path = (
        pathlib.Path(__file__).resolve().parents[2]
        / "script"
        / "the_importance_of_being_earnest.txt"
    )
    script = parse_script(path.read_text(encoding="utf-8"))
    assert script.title.startswith("The Importance of Being Earnest")
    assert "ALGERNON" in script.characters
    assert "LANE" in script.characters
    assert "JACK" in script.characters
    assert len(script.scenes) == 2
