"""
Tests for SessionManager
"""
import pytest
import json
import tempfile
from pathlib import Path
from src.session_manager import SessionManager, SessionData


class TestSessionData:
    """Tests for SessionData dataclass"""

    def test_to_dict(self):
        data = SessionData(
            session_id="test",
            cookies=[{"name": "token", "value": "abc"}],
            local_storage={"key": "value"},
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            metadata={"user": "test"},
        )
        result = data.to_dict()
        assert result["session_id"] == "test"
        assert result["cookies"] == [{"name": "token", "value": "abc"}]
        assert result["local_storage"] == {"key": "value"}

    def test_from_dict(self):
        data = {
            "session_id": "test",
            "cookies": [{"name": "x", "value": "y"}],
            "local_storage": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "metadata": {},
        }
        session = SessionData.from_dict(data)
        assert session.session_id == "test"
        assert session.cookies == [{"name": "x", "value": "y"}]

    def test_from_dict_with_defaults(self):
        data = {"session_id": "minimal"}
        session = SessionData.from_dict(data)
        assert session.session_id == "minimal"
        assert session.cookies == []
        assert session.local_storage == {}


class TestSessionManager:
    """Tests for SessionManager"""

    def test_initialization(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(storage_dir=tmpdir)
            assert manager.storage_dir == Path(tmpdir)
            assert manager.storage_dir.exists()

    def test_get_session_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(storage_dir=tmpdir)
            path = manager._get_session_path("test_session")
            assert path.name == "test_session.json"
            assert path.parent == manager.storage_dir

    def test_get_session_path_sanitizes_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(storage_dir=tmpdir)
            path = manager._get_session_path("test/session/../bad")
            assert "/" not in path.name
            assert ".." not in path.name

    def test_get_session_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(storage_dir=tmpdir)
            result = manager.get_session("nonexistent")
            assert result is None

    def test_list_sessions_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(storage_dir=tmpdir)
            sessions = manager.list_sessions()
            assert sessions == []

    def test_list_sessions_from_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(storage_dir=tmpdir)
            # Create session files manually
            for name in ["session1", "session2"]:
                path = manager._get_session_path(name)
                with open(path, "w") as f:
                    json.dump({"session_id": name}, f)

            sessions = manager.list_sessions()
            assert "session1" in sessions
            assert "session2" in sessions

    def test_delete_session_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(storage_dir=tmpdir)
            result = manager.delete_session("nonexistent")
            assert result is False

    def test_delete_session_from_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(storage_dir=tmpdir)
            # Create session file
            path = manager._get_session_path("to_delete")
            with open(path, "w") as f:
                json.dump({"session_id": "to_delete"}, f)

            assert path.exists()
            result = manager.delete_session("to_delete")
            assert result is True
            assert not path.exists()

    def test_clear_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(storage_dir=tmpdir)
            # Create session files
            for name in ["s1", "s2", "s3"]:
                path = manager._get_session_path(name)
                with open(path, "w") as f:
                    json.dump({"session_id": name}, f)

            count = manager.clear_all()
            assert count == 3
            assert manager.list_sessions() == []

    def test_get_session_from_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(storage_dir=tmpdir)
            # Create session file
            path = manager._get_session_path("test")
            session_data = {
                "session_id": "test",
                "cookies": [{"name": "c", "value": "v"}],
                "local_storage": {"k": "v"},
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "metadata": {"x": 1},
            }
            with open(path, "w") as f:
                json.dump(session_data, f)

            result = manager.get_session("test")
            assert result is not None
            assert result.session_id == "test"
            assert len(result.cookies) == 1
            assert result.local_storage == {"k": "v"}
