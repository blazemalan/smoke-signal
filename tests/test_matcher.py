"""Tests for the speaker identification matcher."""

import sys
from unittest.mock import MagicMock

import numpy as np
import pytest


@pytest.fixture
def matcher(monkeypatch):
    """Stub torch before importing matcher."""
    monkeypatch.setitem(sys.modules, "torch", MagicMock())

    from smoke_signal.enrollment import matcher
    return matcher


def test_single_match_above_threshold(matcher):
    """A clear single match above threshold returns {label: name}."""
    speaker_embeddings = {
        "SPEAKER_00": np.array([0.8, 0.6])
    }
    profile_embeddings = {
        "Alice": np.array([1.0, 0.0])
    }
    # Dot product is 0.8 * 1.0 + 0.6 * 0.0 = 0.8 (>= 0.70)
    mapping = matcher._match_speakers(speaker_embeddings, profile_embeddings)
    assert mapping == {"SPEAKER_00": "Alice"}


def test_below_threshold_excluded(matcher):
    """A pair below 0.70 is excluded from the mapping."""
    speaker_embeddings = {
        "SPEAKER_00": np.array([0.6, 0.8])
    }
    profile_embeddings = {
        "Alice": np.array([1.0, 0.0])
    }
    # Dot product is 0.6 * 1.0 + 0.8 * 0.0 = 0.6 (< 0.70)
    mapping = matcher._match_speakers(speaker_embeddings, profile_embeddings)
    assert mapping == {}


def test_higher_scoring_speaker_wins(matcher):
    """
    When two speakers both score highest against the SAME profile,
    the higher-scoring speaker wins and the other is left unassigned
    (no duplicate profile assignment).
    """
    speaker_embeddings = {
        "SPEAKER_00": np.array([0.9, 0.43588989]),  # Dot product with Alice is 0.9
        "SPEAKER_01": np.array([0.8, 0.6]),         # Dot product with Alice is 0.8
    }
    profile_embeddings = {
        "Alice": np.array([1.0, 0.0])
    }
    mapping = matcher._match_speakers(speaker_embeddings, profile_embeddings)
    assert mapping == {"SPEAKER_00": "Alice"}
    assert "SPEAKER_01" not in mapping


def test_empty_embeddings(matcher):
    """Empty speaker_embeddings returns an empty dict."""
    speaker_embeddings = {}
    profile_embeddings = {
        "Alice": np.array([1.0, 0.0])
    }
    mapping = matcher._match_speakers(speaker_embeddings, profile_embeddings)
    assert mapping == {}

    # Empty profile embeddings also returns an empty dict
    mapping2 = matcher._match_speakers({"SPEAKER_00": np.array([1.0, 0.0])}, {})
    assert mapping2 == {}
