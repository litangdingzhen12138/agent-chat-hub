"""Codex-CLI JSONL 解析器"""

from __future__ import annotations

import json
from collections import defaultdict
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


class CodexCliParser(BaseParser):
    """Codex-CLI 聊天记录解析器

    支持两种格式:
    1. ~/.codex/history.jsonl - 简单历史记录
    2. ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl - 完整会话记录
    """

    def __init__(self, codex_dir: str | Path):
        self.codex_dir = Path(codex_dir)
        # 如果传入的是 history.jsonl 文件，取其父目录
        if self.codex_dir.is_file() and self.codex_dir.name == "history.jsonl":
            self.codex_dir = self.codex_dir.parent

        self.history_file = self.codex_dir / "history.jsonl"
        self.sessions_dir = self.codex_dir / "sessions"

        self._sessions_cache: list[Session] | None = None

    def get_source(self) -> Source:
        sessions = self.get_sessions()
        return Source(
            id=SourceType.CODEX_CLI,
            name="Codex CLI",
            available=len(sessions) > 0,
            path=str(self.codex_dir),
            session_count=len(sessions),
        )

    def get_sessions(self) -> list[Session]:
        if self._sessions_cache is not None:
            return self._sessions_cache

        sessions = []

        # 1. 扫描 rollout 文件（完整会话）
        if self.sessions_dir.exists():
            sessions.extend(self._scan_rollout_files())

        # 2. 扫描 history.jsonl（简单历史）
        if self.history_file.exists():
            history_sessions = self._scan_history_file()
            # 去重：如果 rollout 中已有相同 session_id，跳过
            existing_ids = {s.id for s in sessions}
            for s in history_sessions:
                if s.id not in existing_ids:
                    sessions.append(s)

        # 按创建时间倒序（统一去除时区信息）
        for s in sessions:
            if s.created_at and s.created_at.tzinfo:
                s.created_at = s.created_at.replace(tzinfo=None)
            if s.updated_at and s.updated_at.tzinfo:
                s.updated_at = s.updated_at.replace(tzinfo=None)

        sessions.sort(
            key=lambda s: s.created_at or datetime.min, reverse=True
        )

        self._sessions_cache = sessions
        return sessions

    def get_messages(self, session_id: str) -> list[Message]:
        # 先在 rollout 文件中查找
        rollout_file = self._find_rollout_file(session_id)
        if rollout_file:
            return self._parse_rollout_messages(rollout_file)

        # 再从 history.jsonl 中查找
        return self._parse_history_messages(session_id)

    def search(self, query: str) -> list[dict]:
        results = []
        query_lower = query.lower()

        for session in self.get_sessions():
            messages = self.get_messages(session.id)
            for msg in messages:
                for block in msg.content:
                    if block.type == ContentBlockType.TEXT and query_lower in block.content.lower():
                        idx = block.content.lower().find(query_lower)
                        start = max(0, idx - 50)
                        end = min(len(block.content), idx + len(query) + 50)
                        matched = block.content[start:end]

                        results.append({
                            "session_id": session.id,
                            "session_title": session.title,
                            "message_id": msg.id,
                            "message_role": msg.role.value,
                            "matched_text": matched,
                            "timestamp": msg.timestamp,
                        })
                        break

        return results

    # ============ Rollout 文件处理 ============

    def _scan_rollout_files(self) -> list[Session]:
        """扫描所有 rollout 文件"""
        sessions = []
        for jsonl_file in self.sessions_dir.rglob("rollout-*.jsonl"):
            session = self._parse_rollout_metadata(jsonl_file)
            if session:
                sessions.append(session)
        return sessions

    def _parse_rollout_metadata(self, jsonl_file: Path) -> Session | None:
        """从 rollout 文件解析会话元数据"""
        try:
            session_id = None
            first_user_text = ""
            created_at = None
            msg_count = 0
            cwd_path = ""

            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    msg_type = data.get("type", "")
                    payload = data.get("payload", {})

                    # 提取 session_id 和 cwd
                    if msg_type == "session_meta" and not session_id:
                        session_id = payload.get("id", "")
                        cwd_path = payload.get("cwd", "")
                        ts = payload.get("timestamp", "")
                        if ts:
                            try:
                                created_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                            except (ValueError, TypeError):
                                pass

                    # 提取用户消息作为标题
                    if msg_type == "response_item" and payload.get("role") == "user":
                        content = payload.get("content", [])
                        if isinstance(content, list):
                            for c in content:
                                if isinstance(c, dict) and c.get("type") == "input_text":
                                    text = c.get("text", "").strip()
                                    # 跳过系统消息
                                    if text and not text.startswith("<"):
                                        if not first_user_text:
                                            first_user_text = text
                                        msg_count += 1
                                    break

                    if msg_type == "response_item" and payload.get("role") == "assistant":
                        msg_count += 1

            if not session_id:
                # 从文件名提取
                fname = jsonl_file.stem  # rollout-2026-05-17T09-08-23-019e337a-...
                parts = fname.split("-", 5)
                if len(parts) >= 6:
                    session_id = parts[5]
                else:
                    session_id = fname

            if not created_at:
                created_at = datetime.fromtimestamp(jsonl_file.stat().st_mtime)

            # 标题
            if first_user_text:
                title = first_user_text[:60]
                if len(first_user_text) > 60:
                    title += "..."
            else:
                title = f"Codex 会话 {session_id[:8]}"

            return Session(
                id=session_id,
                source=SourceType.CODEX_CLI,
                title=title,
                message_count=msg_count,
                created_at=created_at,
                updated_at=created_at,
                metadata={
                    "file": str(jsonl_file),
                    "format": "rollout",
                    "project_path": cwd_path,  # 提取项目路径
                },
            )
        except Exception:
            return None

    def _find_rollout_file(self, session_id: str) -> Path | None:
        """根据 session_id 查找 rollout 文件"""
        if not self.sessions_dir.exists():
            return None
        for jsonl_file in self.sessions_dir.rglob("rollout-*.jsonl"):
            # 检查文件名或内容中是否包含 session_id
            if session_id in jsonl_file.name:
                return jsonl_file
            # 快速检查文件内容
            try:
                with open(jsonl_file, "r", encoding="utf-8") as f:
                    for i, line in enumerate(f):
                        if i > 10:  # 只检查前几行
                            break
                        data = json.loads(line.strip())
                        if data.get("payload", {}).get("id") == session_id:
                            return jsonl_file
            except Exception:
                continue
        return None

    def _parse_rollout_messages(self, jsonl_file: Path) -> list[Message]:
        """解析 rollout 文件中的消息"""
        messages = []
        msg_index = 0

        try:
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if data.get("type") != "response_item":
                        continue

                    payload = data.get("payload", {})
                    role_str = payload.get("role", "")

                    # 只处理 user 和 assistant
                    if role_str not in ("user", "assistant"):
                        continue

                    content_list = payload.get("content", [])
                    blocks = []
                    text_type = "input_text" if role_str == "user" else "output_text"

                    for c in content_list:
                        if not isinstance(c, dict):
                            continue
                        if c.get("type") == text_type:
                            text = c.get("text", "").strip()
                            if text and not text.startswith("<"):
                                blocks.append(
                                    ContentBlock(type=ContentBlockType.TEXT, content=text)
                                )
                        elif c.get("type") == "summary_text":
                            text = c.get("text", "").strip()
                            if text:
                                blocks.append(
                                    ContentBlock(type=ContentBlockType.TEXT, content=text)
                                )

                    if not blocks:
                        continue

                    timestamp = None
                    ts = data.get("timestamp", "")
                    if ts:
                        try:
                            timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        except (ValueError, TypeError):
                            pass

                    role = MessageRole.USER if role_str == "user" else MessageRole.ASSISTANT

                    messages.append(Message(
                        id=f"rollout-{msg_index}",
                        role=role,
                        content=blocks,
                        timestamp=timestamp,
                    ))
                    msg_index += 1

        except Exception:
            pass

        return messages

    # ============ History 文件处理 ============

    def _scan_history_file(self) -> list[Session]:
        """扫描 history.jsonl"""
        sessions = []
        entries: dict[str, list[dict]] = defaultdict(list)

        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        sid = data.get("session_id", "unknown")
                        entries[sid].append(data)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            return sessions

        for sid, session_entries in entries.items():
            if not session_entries:
                continue

            session_entries.sort(key=lambda e: e.get("ts", 0))
            first = session_entries[0]
            last = session_entries[-1]

            created_at = None
            updated_at = None
            if first.get("ts"):
                try:
                    created_at = datetime.fromtimestamp(first["ts"])
                except (ValueError, TypeError, OSError):
                    pass
            if last.get("ts"):
                try:
                    updated_at = datetime.fromtimestamp(last["ts"])
                except (ValueError, TypeError, OSError):
                    pass

            # 提取第一个有意义的用户问题作为标题
            first_text = ""
            for entry in session_entries:
                text = entry.get("text", "").strip()
                # 跳过系统指令和无意义内容
                if not text:
                    continue
                if "# AGENTS.md" in text:
                    continue
                if "<INSTRUCTIONS>" in text:
                    continue
                if text.startswith("[$"):  # 插件指令
                    continue
                if text.startswith("# Files mentioned"):
                    continue
                if len(text) < 2:  # 太短的无意义
                    continue
                first_text = text
                break

            title = first_text[:60].strip()
            if len(first_text) > 60:
                title += "..."

            if not title:
                title = f"Codex 会话 {sid[:8]}"

            sessions.append(Session(
                id=sid,
                source=SourceType.CODEX_CLI,
                title=title,
                message_count=len(session_entries),
                created_at=created_at,
                updated_at=updated_at,
                metadata={"format": "history"},
            ))

        return sessions

    def _parse_history_messages(self, session_id: str) -> list[Message]:
        """从 history.jsonl 解析消息"""
        entries = []

        if not self.history_file.exists():
            return []

        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("session_id") == session_id:
                            entries.append(data)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            return []

        entries.sort(key=lambda e: e.get("ts", 0))

        messages = []
        for i, entry in enumerate(entries):
            text = entry.get("text", "")
            if not text.strip():
                continue

            timestamp = None
            if entry.get("ts"):
                try:
                    timestamp = datetime.fromtimestamp(entry["ts"])
                except (ValueError, TypeError, OSError):
                    pass

            role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT

            messages.append(Message(
                id=f"history-{session_id}-{i}",
                role=role,
                content=[ContentBlock(type=ContentBlockType.TEXT, content=text)],
                timestamp=timestamp,
            ))

        return messages
