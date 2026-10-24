"""Fuzzy matching of an actor's spoken line against the expected script line.

Deterministic, not LLM-based: the actor's STT transcript is compared directly
against the expected text with string similarity. This keeps cue delivery and
line-matching decisions rule-based and reproducible, reserving the LLM (used
elsewhere in the pipeline) for understanding free-form voice commands only.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz

# A spoken line scoring at or above this (0-100 scale) counts as a correct
# delivery. Tuned loosely: STT transcription noise and minor paraphrasing
# ("I'm" vs "I am") should still pass; a genuinely different line should not.
DEFAULT_MATCH_THRESHOLD = 70.0

_PUNCTUATION_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Lowercase, strip punctuation, and collapse whitespace for comparison."""
    text = text.lower()
    text = _PUNCTUATION_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def line_match_score(spoken: str, expected: str) -> float:
    """Similarity between spoken and expected text, 0-100 (100 = identical after normalization)."""
    return fuzz.ratio(normalize(spoken), normalize(expected))


def is_line_match(
    spoken: str, expected: str, threshold: float = DEFAULT_MATCH_THRESHOLD
) -> bool:
    """Whether `spoken` is close enough to `expected` to count as a correct delivery."""
    return line_match_score(spoken, expected) >= threshold
