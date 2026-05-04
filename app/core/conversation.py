from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class ConversationStore:
    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = Path.home() / ".manimator" / "conversations.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
                role            TEXT NOT NULL,
                content         TEXT NOT NULL,
                code_snippet    TEXT,
                video_path      TEXT,
                created         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self._conn.commit()

    def new_conversation(self) -> int:
        cur = self._conn.execute("INSERT INTO conversations DEFAULT VALUES")
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        code_snippet: str | None = None,
        video_path: str | None = None,
    ) -> int:
        cur = self._conn.execute(
            """INSERT INTO messages
               (conversation_id, role, content, code_snippet, video_path)
               VALUES (?, ?, ?, ?, ?)""",
            (conversation_id, role, content, code_snippet, video_path),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def update_video_path(self, message_id: int, video_path: str) -> None:
        self._conn.execute(
            "UPDATE messages SET video_path = ? WHERE id = ?",
            (video_path, message_id),
        )
        self._conn.commit()

    def get_messages(self, conversation_id: int) -> list[dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created",
            (conversation_id,),
        )
        return [dict(row) for row in cur.fetchall()]

    def list_conversations(self) -> list[dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT id, created FROM conversations ORDER BY created DESC"
        )
        return [dict(row) for row in cur.fetchall()]

    def delete_conversation(self, conversation_id: int) -> None:
        self._conn.execute(
            "DELETE FROM conversations WHERE id = ?", (conversation_id,)
        )
        self._conn.commit()

    def clear_all(self) -> None:
        self._conn.executescript(
            "DELETE FROM messages; DELETE FROM conversations;"
        )
        self._conn.commit()

    def build_messages_for_request(
        self,
        conversation_id: int,
        system_prompt: str,
        context_limit: int,
        tokens_per_char: float = 0.25,
    ) -> tuple[list[dict[str, str]], bool]:
        """
        Build the messages list for the LLM, applying oldest-first truncation
        to stay under 85% of context_limit tokens.

        Returns (messages_list, was_truncated).
        """
        rows = self.get_messages(conversation_id)

        # Build raw history pairs (role, content)
        history: list[dict[str, str]] = [
            {"role": r["role"], "content": r["content"]} for r in rows
        ]

        threshold = int(context_limit * 0.85)

        def estimate_tokens(msgs: list[dict]) -> int:
            total_chars = sum(len(m["content"]) for m in msgs)
            total_chars += len(system_prompt)
            return int(total_chars * tokens_per_char)

        was_truncated = False
        system_msg = {"role": "system", "content": system_prompt}

        # Keep dropping oldest pairs until we fit
        while len(history) > 2 and estimate_tokens([system_msg] + history) > threshold:
            history.pop(0)
            was_truncated = True

        return [system_msg] + history, was_truncated
