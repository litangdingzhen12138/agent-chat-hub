"""OpenCode SQLite 解析器"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from ..models import (
    ContentBlock,
    ContentBlockType,
    Message,
    MessageRole,
    Session,
    Source,
    SourceType,
)
from .base import BaseParser


class OpenCodeParser(BaseParser):
    """OpenCode 聊天记录解析器

    OpenCode 实际存储格式:
    - SQLite 数据库，位于 ~/.local/share/opencode/opencode.db
    - 表: session, message, part
    - message.data 是 JSON，包含 role 等信息
    - part.data 是 JSON，包含 type, text 等信息
    """

    def __init__(self, db_path: str | Path, source_id: str = "opencode"):
        self.db_path = Path(db_path)
        self.source_id = source_id
        self._sessions_cache: list[Session] | None = None

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def get_source(self) -> Source:
        sessions = self.get_sessions()
        return Source(
            id=self.source_id,
            name=self.source_id.split(":")[-1] if ":" in self.source_id else "OpenCode",
            available=len(sessions) > 0,
            path=str(self.db_path),
            session_count=len(sessions),
        )

    def get_sessions(self) -> list[Session]:
        if self._sessions_cache is not None:
            return self._sessions_cache

        sessions = []
        if not self.db_path.exists():
            return sessions

        try:
            conn = self._get_connection()
            # OpenCode 使用 session 表（不是 sessions）
            cursor = conn.execute(
                """
                SELECT id, title, parent_id, directory, path,
                       model, cost, tokens_input, tokens_output,
                       time_created, time_updated
                FROM session
                WHERE parent_id IS NULL
                ORDER BY time_created DESC
                """
            )

            for row in cursor.fetchall():
                session = self._row_to_session(row)
                if session:
                    sessions.append(session)

            conn.close()
        except Exception as e:
            pass

        self._sessions_cache = sessions
        return sessions

    def get_messages(self, session_id: str) -> list[Message]:
        messages = []
        if not self.db_path.exists():
            return messages

        try:
            conn = self._get_connection()
            # 查询该会话的所有消息
            cursor = conn.execute(
                """
                SELECT id, session_id, data, time_created, time_updated
                FROM message
                WHERE session_id = ?
                ORDER BY time_created ASC
                """,
                (session_id,),
            )

            for row in cursor.fetchall():
                message = self._row_to_message(row, conn)
                if message:
                    messages.append(message)

            conn.close()
        except Exception:
            pass

        return messages

    def search(self, query: str) -> list[dict]:
        results = []
        if not self.db_path.exists():
            return results

        query_lower = query.lower()

        try:
            conn = self._get_connection()
            # 在 part 表中搜索文本内容
            cursor = conn.execute(
                """
                SELECT p.id, p.message_id, p.session_id, p.data,
                       s.title as session_title
                FROM part p
                JOIN session s ON p.session_id = s.id
                WHERE p.data LIKE ?
                ORDER BY p.time_created DESC
                LIMIT 100
                """,
                (f"%{query_lower}%",),
            )

            for row in cursor.fetchall():
                try:
                    part_data = json.loads(row["data"]) if row["data"] else {}
                except json.JSONDecodeError:
                    continue

                text = part_data.get("text", "")
                if query_lower not in text.lower():
                    continue

                idx = text.lower().find(query_lower)
                start = max(0, idx - 50)
                end = min(len(text), idx + len(query) + 50)
                matched = text[start:end]

                timestamp = None
                time_info = part_data.get("time", {})
                if isinstance(time_info, dict) and time_info.get("start"):
                    try:
                        timestamp = datetime.fromtimestamp(
                            time_info["start"] / 1000
                        )
                    except (ValueError, TypeError, OSError):
                        pass

                results.append({
                    "session_id": row["session_id"],
                    "session_title": row["session_title"] or "",
                    "message_id": row["message_id"],
                    "message_role": "user",  # 简化处理
                    "matched_text": matched,
                    "timestamp": timestamp,
                })

            conn.close()
        except Exception:
            pass

        return results

    def _row_to_session(self, row: sqlite3.Row) -> Session | None:
        """将数据库行转换为 Session"""
        try:
            created_at = None
            updated_at = None

            if row["time_created"]:
                try:
                    created_at = datetime.fromtimestamp(
                        row["time_created"] / 1000
                    )
                except (ValueError, TypeError, OSError):
                    pass

            if row["time_updated"]:
                try:
                    updated_at = datetime.fromtimestamp(
                        row["time_updated"] / 1000
                    )
                except (ValueError, TypeError, OSError):
                    pass

            # 统计消息数量
            msg_count = self._count_messages(row["id"])

            # 获取目录路径
            directory = row["directory"] or ""
            path = row["path"] or ""

            return Session(
                id=row["id"],
                source=self.source_id,
                title=row["title"] or "Untitled",
                message_count=msg_count,
                created_at=created_at,
                updated_at=updated_at,
                metadata={
                    "directory": directory,
                    "path": path,
                    "project_path": directory,  # 用于目录树分组
                    "model": row["model"] or "",
                    "cost": row["cost"] or 0.0,
                    "tokens_input": row["tokens_input"] or 0,
                    "tokens_output": row["tokens_output"] or 0,
                },
            )
        except Exception:
            return None

    def _count_messages(self, session_id: str) -> int:
        """统计会话的消息数量"""
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                "SELECT COUNT(*) FROM message WHERE session_id = ?",
                (session_id,),
            )
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    def _row_to_message(self, row: sqlite3.Row, conn: sqlite3.Connection) -> Message | None:
        """将数据库行转换为 Message"""
        try:
            msg_data = json.loads(row["data"]) if row["data"] else {}

            # 解析角色
            role_str = msg_data.get("role", "user")
            try:
                role = MessageRole(role_str)
            except ValueError:
                role = MessageRole.USER

            # 获取该消息的所有 part
            content_blocks = self._get_message_parts(row["id"], conn)

            if not content_blocks:
                return None

            # 解析时间戳
            timestamp = None
            time_info = msg_data.get("time", {})
            if isinstance(time_info, dict) and time_info.get("created"):
                try:
                    timestamp = datetime.fromtimestamp(
                        time_info["created"] / 1000
                    )
                except (ValueError, TypeError, OSError):
                    pass

            # 获取模型信息
            model = msg_data.get("modelID", "")

            return Message(
                id=row["id"],
                role=role,
                content=content_blocks,
                timestamp=timestamp,
                model=model,
            )
        except Exception:
            return None

    def _get_message_parts(self, message_id: str, conn: sqlite3.Connection) -> list[ContentBlock]:
        """获取消息的所有 part"""
        blocks = []

        try:
            cursor = conn.execute(
                """
                SELECT id, data
                FROM part
                WHERE message_id = ?
                ORDER BY time_created ASC
                """,
                (message_id,),
            )

            for row in cursor.fetchall():
                try:
                    part_data = json.loads(row["data"]) if row["data"] else {}
                except json.JSONDecodeError:
                    continue

                part_type = part_data.get("type", "")

                if part_type == "text":
                    text = part_data.get("text", "")
                    if text.strip():
                        blocks.append(
                            ContentBlock(
                                type=ContentBlockType.TEXT,
                                content=text,
                            )
                        )

                elif part_type == "tool_use":
                    tool_name = part_data.get("name", "unknown")
                    tool_input = part_data.get("input", {})
                    blocks.append(
                        ContentBlock(
                            type=ContentBlockType.TOOL_USE,
                            content=json.dumps(
                                tool_input, ensure_ascii=False, indent=2
                            ),
                            metadata={"tool_name": tool_name},
                        )
                    )

                elif part_type == "tool_result":
                    result = part_data.get("content", "")
                    is_error = part_data.get("is_error", False)
                    blocks.append(
                        ContentBlock(
                            type=ContentBlockType.TOOL_RESULT,
                            content=str(result),
                            metadata={"is_error": is_error},
                        )
                    )

                elif part_type == "thinking":
                    thinking = part_data.get("thinking", "")
                    if thinking.strip():
                        blocks.append(
                            ContentBlock(
                                type=ContentBlockType.THINKING,
                                content=thinking,
                            )
                        )

        except Exception:
            pass

        return blocks
