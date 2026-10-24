import pytest

from line_partner.parser import parse_script
from line_partner.state_machine import Done, LinePartnerSession, Listen, Say

SCRIPT_TEXT = """\
TITLE: T
SOURCE: S

SCENE: One

ALICE: Hi Bob.
BOB: Hi Alice.
ALICE: How are you?
BOB: Good, you?

SCENE: Two

ALICE: Let's go.
BOB: Okay.
"""


def make_session() -> LinePartnerSession:
    script = parse_script(SCRIPT_TEXT)
    return LinePartnerSession(script, actor_character="bob")


def test_unknown_character_raises():
    script = parse_script(SCRIPT_TEXT)
    with pytest.raises(ValueError, match="not a character"):
        LinePartnerSession(script, actor_character="CAROL")


def test_actor_character_normalized_case_insensitively():
    session = make_session()
    assert session.actor_character == "BOB"


def test_start_says_npc_lines_then_listens_for_actor():
    session = make_session()
    actions = session.start()
    assert actions == [
        Say(character="ALICE", text="Hi Bob."),
        Listen(character="BOB", expected_text="Hi Alice."),
    ]


def test_current_expected_line_tracks_the_listen_target():
    session = make_session()
    session.start()
    expected = session.current_expected_line()
    assert expected is not None
    assert expected.text == "Hi Alice."


def test_wrong_line_does_not_advance():
    session = make_session()
    session.start()
    matched, actions = session.submit_line("that is not my line at all")
    assert matched is False
    assert actions == []
    assert session.current_expected_line().text == "Hi Alice."


def test_correct_line_advances_to_next_cue():
    session = make_session()
    session.start()
    matched, actions = session.submit_line("Hi Alice.")
    assert matched is True
    assert actions == [
        Say(character="ALICE", text="How are you?"),
        Listen(character="BOB", expected_text="Good, you?"),
    ]


def test_crosses_scene_boundary_seamlessly():
    session = make_session()
    session.start()
    session.submit_line("Hi Alice.")
    matched, actions = session.submit_line("Good, you?")
    assert matched is True
    assert actions == [
        Say(character="ALICE", text="Let's go."),
        Listen(character="BOB", expected_text="Okay."),
    ]


def test_reaches_done_at_end_of_script():
    session = make_session()
    session.start()
    session.submit_line("Hi Alice.")
    session.submit_line("Good, you?")
    matched, actions = session.submit_line("Okay.")
    assert matched is True
    assert actions == [Done()]
    assert session.current_expected_line() is None


def test_submit_line_after_done_raises():
    session = make_session()
    session.start()
    session.submit_line("Hi Alice.")
    session.submit_line("Good, you?")
    session.submit_line("Okay.")
    with pytest.raises(RuntimeError, match="no line is currently expected"):
        session.submit_line("anything")


def test_line_hint_returns_first_words_of_expected_line():
    session = make_session()
    session.start()
    assert session.line_hint(n_words=1) == "Hi"


def test_again_returns_none_before_any_npc_line():
    script = parse_script(SCRIPT_TEXT)
    # ALICE goes first every scene in this fixture, so play ALICE to start
    # with no prior NPC line spoken yet.
    session = LinePartnerSession(script, actor_character="alice")
    session.start()
    assert session.again() is None


def test_again_repeats_last_npc_line():
    session = make_session()
    session.start()
    repeated = session.again()
    assert repeated == Say(character="ALICE", text="Hi Bob.")


def test_from_the_top_resets_to_current_scene_start():
    session = make_session()
    session.start()
    session.submit_line("Hi Alice.")
    actions = session.from_the_top()
    assert actions == [
        Say(character="ALICE", text="Hi Bob."),
        Listen(character="BOB", expected_text="Hi Alice."),
    ]


def test_skip_to_scene_jumps_directly():
    session = make_session()
    session.start()
    actions = session.skip_to_scene(2)
    assert actions == [
        Say(character="ALICE", text="Let's go."),
        Listen(character="BOB", expected_text="Okay."),
    ]


def test_skip_to_invalid_scene_raises():
    session = make_session()
    with pytest.raises(ValueError, match="does not exist"):
        session.skip_to_scene(99)
