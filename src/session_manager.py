"""
Session Manager - Cookie and session persistence
"""
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from loguru import logger


@dataclass
class SessionData:
    """Session data container"""
    session_id: str
    cookies: list[dict]
    local_storage: dict[str, str]
    created_at: str
    updated_at: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "cookies": self.cookies,
            "local_storage": self.local_storage,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionData":
        return cls(
            session_id=data["session_id"],
            cookies=data.get("cookies", []),
            local_storage=data.get("local_storage", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            metadata=data.get("metadata", {}),
        )


class SessionManager:
    """
    Manages browser session persistence (cookies, local storage).

    Example:
        manager = SessionManager(storage_dir="./sessions")

        # Save session after login
        await manager.save_session(context, "user_session")

        # Load session on next run
        await manager.load_session(context, "user_session")
    """

    def __init__(self, storage_dir: str = "./sessions"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, SessionData] = {}

    def _get_session_path(self, session_id: str) -> Path:
        """Get file path for session"""
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
        return self.storage_dir / f"{safe_id}.json"

    async def save_session(
        self,
        context,  # BrowserContext
        session_id: str,
        metadata: Optional[dict] = None,
    ) -> SessionData:
        """
        Save browser context session (cookies, storage).

        Args:
            context: Playwright BrowserContext
            session_id: Unique identifier for the session
            metadata: Optional metadata to store with session
        """
        now = datetime.utcnow().isoformat() + "Z"

        # Get cookies
        cookies = await context.cookies()

        # Get local storage (requires a page)
        local_storage = {}
        pages = context.pages
        if pages:
            try:
                storage = await pages[0].evaluate("""
                    () => {
                        const items = {};
                        for (let i = 0; i < localStorage.length; i++) {
                            const key = localStorage.key(i);
                            items[key] = localStorage.getItem(key);
                        }
                        return items;
                    }
                """)
                local_storage = storage or {}
            except Exception as e:
                logger.debug(f"Could not get localStorage: {e}")

        # Create session data
        existing = self._sessions.get(session_id)
        session_data = SessionData(
            session_id=session_id,
            cookies=cookies,
            local_storage=local_storage,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            metadata=metadata or (existing.metadata if existing else {}),
        )

        # Save to memory
        self._sessions[session_id] = session_data

        # Save to file
        session_path = self._get_session_path(session_id)
        with open(session_path, "w", encoding="utf-8") as f:
            json.dump(session_data.to_dict(), f, indent=2, ensure_ascii=False)

        logger.info(f"Session saved: {session_id} ({len(cookies)} cookies)")
        return session_data

    async def load_session(
        self,
        context,  # BrowserContext
        session_id: str,
    ) -> Optional[SessionData]:
        """
        Load saved session into browser context.

        Args:
            context: Playwright BrowserContext
            session_id: Session identifier to load

        Returns:
            SessionData if found and loaded, None otherwise
        """
        # Try memory cache first
        session_data = self._sessions.get(session_id)

        # Try file if not in memory
        if not session_data:
            session_path = self._get_session_path(session_id)
            if session_path.exists():
                try:
                    with open(session_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        session_data = SessionData.from_dict(data)
                        self._sessions[session_id] = session_data
                except Exception as e:
                    logger.error(f"Failed to load session file: {e}")
                    return None

        if not session_data:
            logger.warning(f"Session not found: {session_id}")
            return None

        # Add cookies to context
        if session_data.cookies:
            await context.add_cookies(session_data.cookies)
            logger.debug(f"Loaded {len(session_data.cookies)} cookies")

        # Restore local storage (requires navigation first)
        if session_data.local_storage:
            pages = context.pages
            if pages:
                try:
                    for key, value in session_data.local_storage.items():
                        await pages[0].evaluate(
                            f"localStorage.setItem({json.dumps(key)}, {json.dumps(value)})"
                        )
                    logger.debug(f"Loaded {len(session_data.local_storage)} localStorage items")
                except Exception as e:
                    logger.debug(f"Could not restore localStorage: {e}")

        logger.info(f"Session loaded: {session_id}")
        return session_data

    def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session data without loading into browser"""
        if session_id in self._sessions:
            return self._sessions[session_id]

        session_path = self._get_session_path(session_id)
        if session_path.exists():
            try:
                with open(session_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return SessionData.from_dict(data)
            except Exception as e:
                logger.error(f"Failed to read session: {e}")

        return None

    def delete_session(self, session_id: str) -> bool:
        """Delete a saved session"""
        # Remove from memory
        if session_id in self._sessions:
            del self._sessions[session_id]

        # Remove file
        session_path = self._get_session_path(session_id)
        if session_path.exists():
            try:
                session_path.unlink()
                logger.info(f"Session deleted: {session_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete session file: {e}")
                return False

        return False

    def list_sessions(self) -> list[str]:
        """List all saved session IDs"""
        sessions = set(self._sessions.keys())

        # Add sessions from files
        for path in self.storage_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "session_id" in data:
                        sessions.add(data["session_id"])
            except Exception:
                pass

        return sorted(sessions)

    def clear_all(self) -> int:
        """Delete all saved sessions"""
        count = 0
        for session_id in self.list_sessions():
            if self.delete_session(session_id):
                count += 1
        return count
