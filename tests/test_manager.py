import json
import sys
from datetime import datetime
from unittest.mock import MagicMock

import numpy as np
import pytest

@pytest.fixture
def manager(monkeypatch):
    """Stub torch to avoid loading heavy dependencies, then import manager."""
    monkeypatch.setitem(sys.modules, "torch", MagicMock())
    import smoke_signal.enrollment.manager as manager
    return manager

def create_mock_profile(path, name, num_samples=1):
    """Helper to create a mock profile JSON file."""
    profile_data = {
        "name": name,
        "created": datetime.now().isoformat(),
        "updated": datetime.now().isoformat(),
        "num_samples": num_samples,
        "embedding": [0.1, 0.2, 0.3],
        "embedding_model": "pyannote/embedding",
        "sample_sources": [f"{name.lower()}_audio.wav"]
    }
    with open(path, "w") as f:
        json.dump(profile_data, f)
    return profile_data

def test_list_profiles(manager, tmp_path):
    # Create two profiles
    bob_path = tmp_path / "bob.json"
    alice_path = tmp_path / "alice.json"

    create_mock_profile(bob_path, "Bob", 2)
    create_mock_profile(alice_path, "Alice", 1)

    profiles = manager.list_profiles(tmp_path)

    # Should be sorted by filename (alice.json then bob.json)
    assert len(profiles) == 2
    assert profiles[0]["name"] == "Alice"
    assert profiles[1]["name"] == "Bob"

    # Check expected keys
    for profile in profiles:
        assert "name" in profile
        assert "num_samples" in profile
        assert "created" in profile
        assert "updated" in profile
        assert "sources" in profile

def test_delete_profile(manager, tmp_path):
    # Create a profile
    bob_path = tmp_path / "bob.json"
    create_mock_profile(bob_path, "Bob")

    # Verify deletion of existing profile
    assert manager.delete_profile("Bob", tmp_path) is True
    assert not bob_path.exists()

    # Verify deletion of non-existing profile
    assert manager.delete_profile("Missing", tmp_path) is False

def test_load_all_embeddings(manager, tmp_path):
    bob_path = tmp_path / "bob.json"
    create_mock_profile(bob_path, "Bob")

    embeddings = manager.load_all_embeddings(tmp_path)

    assert "Bob" in embeddings
    assert isinstance(embeddings["Bob"], np.ndarray)
    np.testing.assert_allclose(embeddings["Bob"], np.array([0.1, 0.2, 0.3]))

def test_missing_directory(manager, tmp_path):
    missing_dir = tmp_path / "does_not_exist"

    # All three functions should gracefully handle missing directories
    assert manager.list_profiles(missing_dir) == []
    assert manager.delete_profile("Anyone", missing_dir) is False
    assert manager.load_all_embeddings(missing_dir) == {}
