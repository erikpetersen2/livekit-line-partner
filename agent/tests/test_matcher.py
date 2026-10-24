from line_partner.matcher import is_line_match, line_match_score, normalize
from line_partner.script_model import Line


def test_normalize_lowercases_and_strips_punctuation():
    assert normalize("Hello, World!") == "hello world"


def test_normalize_collapses_whitespace():
    assert normalize("  hello   there  ") == "hello there"


def test_exact_match_scores_100():
    assert line_match_score("Hello there.", "Hello there.") == 100.0


def test_case_and_punctuation_insensitive_match():
    assert is_line_match("hello there", "Hello there.")


def test_normalization_handles_missing_punctuation_from_stt():
    # STT transcripts often omit commas/periods entirely.
    assert is_line_match(
        "I didn't think it polite to listen sir",
        "I didn't think it polite to listen, sir.",
    )


def test_minor_word_difference_still_matches():
    assert is_line_match(
        "I'm sorry for that for your sake",
        "I'm sorry for that, for your sake.",
    )


def test_spelling_variant_near_miss_still_matches():
    # British vs. American spelling, as a real STT model might transcribe it.
    assert is_line_match(
        "Good heavens is marriage so demoralizing as that",
        "Good heavens! Is marriage so demoralising as that?",
    )


def test_wrong_line_does_not_match():
    assert not is_line_match(
        "Perfectly horrid never speak to one of them",
        "Did you hear what I was playing, Lane?",
    )


def test_empty_spoken_text_does_not_match():
    assert not is_line_match("", "Did you hear what I was playing, Lane?")


def test_threshold_is_configurable():
    spoken = "Good heavens is marriage so demoralizing as that"
    expected = "Good heavens! Is marriage so demoralising as that?"
    score = line_match_score(spoken, expected)
    assert is_line_match(spoken, expected, threshold=score - 1)
    assert not is_line_match(spoken, expected, threshold=score + 1)


def test_prompt_hint_returns_first_n_words():
    line = Line(character="ALGERNON", text="Did you hear what I was playing, Lane?")
    assert line.prompt_hint(n_words=4) == "Did you hear what"


def test_prompt_hint_handles_short_lines():
    line = Line(character="JACK", text="In the country.")
    assert line.prompt_hint(n_words=4) == "In the country."
