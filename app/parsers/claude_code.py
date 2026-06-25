"""Claude Code JSONL 解析器"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

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


class ClaudeCodeParser(BaseParser):
    """Claude Code 聊天记录解析器

    Claude Code 存储格式:
    - 路径: ~/.claude/projects/<encoded-path>/<session-id>.jsonl
    - 每行一个 JSON 对象
    - 类型: user, assistant, tool_result, mode, permission-mode, file-history-snapshot, attachment
    """

    def __init__(self, projects_dir: str | Path):
        self.projects_dir = Path(projects_dir)
        self._sessions_cache: list[Session] | None = None

    def get_source(self) -> Source:
        sessions = self.get_sessions()
        return Source(
            id=SourceType.CLAUDE_CODE,
            name="Claude Code",
            available=len(sessions) > 0,
            path=str(self.projects_dir),
            session_count=len(sessions),
        )

    def get_sessions(self) -> list[Session]:
        if self._sessions_cache is not None:
            return self._sessions_cache

        sessions = []
        if not self.projects_dir.exists():
            return sessions

        for project_dir in self.iterdir_safe(self.projects_dir):
            if not project_dir.is_dir():
                continue

            project_name = project_dir.name

            for jsonl_file in project_dir.iterdir():
                if jsonl_file.suffix != ".jsonl" or not jsonl_file.is_file():
                    continue

                session_id = jsonl_file.stem
                session = self._parse_session_metadata(
                    jsonl_file, session_id, project_name
                )
                if session:
                    sessions.append(session)

        # 按创建时间倒序排列
        sessions.sort(
            key=lambda s: s.created_at or datetime.min, reverse=True
        )
        self._sessions_cache = sessions
        return sessions

    def get_messages(self, session_id: str) -> list[Message]:
        # 找到对应的 JSONL 文件
        jsonl_file = self._find_session_file(session_id)
        if not jsonl_file:
            return []

        return self._parse_messages(jsonl_file)

    def search(self, query: str) -> list[dict]:
        results = []
        query_lower = query.lower()

        for session in self.get_sessions():
            messages = self.get_messages(session.id)
            for msg in messages:
                for block in msg.content:
                    if query_lower in block.content.lower():
                        # 截取匹配的上下文
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
                        break  # 每条消息只报一次

        return results

    def _find_session_file(self, session_id: str) -> Path | None:
        """查找会话文件"""
        for project_dir in self.iterdir_safe(self.projects_dir):
            if not project_dir.is_dir():
                continue
            jsonl_file = project_dir / f"{session_id}.jsonl"
            if jsonl_file.exists():
                return jsonl_file
        return None

    def _parse_session_metadata(
        self, jsonl_file: Path, session_id: str, project_name: str
    ) -> Session | None:
        """解析会话元数据（只读取前几行）"""
        try:
            created_at = datetime.fromtimestamp(jsonl_file.stat().st_mtime)
            message_count = 0
            first_user_text = ""

            # 解码项目路径: D--PycharmProject-agent----- -> D:/PycharmProject/agent聊天可视化
            project_path = self._decode_project_name(project_name)

            # 快速统计消息数，同时提取第一个用户问题
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        msg_type = data.get("type", "")
                        if msg_type in ("user", "assistant"):
                            message_count += 1

                        # 提取第一个用户的真实问题（非meta、非命令）
                        if (
                            msg_type == "user"
                            and not first_user_text
                            and not data.get("isMeta", False)
                        ):
                            msg_data = data.get("message", {})
                            content = msg_data.get("content", "")
                            if isinstance(content, str) and content.strip():
                                # 跳过命令和系统消息
                                if not content.startswith("<"):
                                    first_user_text = content.strip()
                            elif isinstance(content, list):
                                for block in content:
                                    if isinstance(block, dict) and block.get("type") == "text":
                                        text = block.get("text", "").strip()
                                        if text and not text.startswith("<"):
                                            first_user_text = text
                                            break
                    except json.JSONDecodeError:
                        continue

            # 标题取用户第一段问题的前60个字符
            if first_user_text:
                title = first_user_text[:60]
                if len(first_user_text) > 60:
                    title += "..."
            else:
                title = f"会话 {session_id[:8]}"

            return Session(
                id=session_id,
                source=SourceType.CLAUDE_CODE,
                title=title,
                message_count=message_count,
                created_at=created_at,
                updated_at=created_at,
                metadata={
                    "project": project_name,
                    "project_path": project_path,
                    "file": str(jsonl_file),
                },
            )
        except Exception:
            return None

    @staticmethod
    def _decode_project_name(encoded: str) -> str:
        """解码项目目录名为可读格式
        Claude Code 用 - 替换路径分隔符和特殊字符
        """
        if not encoded:
            return encoded

        # 盘符处理: D-- -> D:\
        if len(encoded) >= 3 and encoded[0].isalpha() and encoded[1:3] == '--':
            encoded = encoded[0] + ":\\" + encoded[3:]
        # 盘符处理: D- -> D:\
        elif len(encoded) >= 2 and encoded[0].isalpha() and encoded[1] == '-':
            encoded = encoded[0] + ":\\" + encoded[2:]

        # 替换 -- 为路径分隔符
        result = encoded.replace("--", "/")

        # 替换单个 - 为路径分隔符（但保留连续的 -----）
        import re
        # 先保护连续 5 个及以上的 -（中文字符编码）
        result = re.sub(r'-{5,}', lambda m: '\x00' * len(m.group()), result)
        # 替换单个 - 为 /
        result = result.replace("-", "/")
        # 恢复连续的 -（保留原样，不作为分隔符）
        result = result.replace('\x00', '')

        # 标准化路径分隔符
        result = result.replace("\\", "/")

        # 清理：移除连续的 / 和尾部的 /
        result = re.sub(r'/+', '/', result)
        result = result.rstrip('/')

        return result

    def _parse_messages(self, jsonl_file: Path) -> list[Message]:
        """解析所有消息"""
        messages = []

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

                    msg_type = data.get("type", "")

                    # 跳过非消息类型
                    if msg_type not in ("user", "assistant"):
                        continue

                    # 跳过 meta 消息（命令回显等）
                    if data.get("isMeta", False):
                        continue

                    # 跳过系统注入的消息（非真实用户输入）
                    if msg_type == "user" and self._is_system_injected(data):
                        continue

                    message = self._parse_single_message(data, msg_type)
                    if message:
                        messages.append(message)

        except Exception:
            pass

        return messages

    @staticmethod
    def _is_system_injected(data: dict[str, Any]) -> bool:
        """判断是否为系统注入的非真实用户消息"""
        msg_data = data.get("message", {})
        content = msg_data.get("content", "")

        # 字符串内容
        if isinstance(content, str):
            stripped = content.strip()
            # 系统命令回显
            if stripped.startswith("<"):
                return True
            # 中断消息
            if stripped.startswith("[Request interrupted"):
                return True
            return False

        # 列表内容 - 检查是否只有 tool_result
        if isinstance(content, list):
            has_text = any(
                isinstance(b, dict) and b.get("type") == "text"
                for b in content
            )
            has_tool_result = any(
                isinstance(b, dict) and b.get("type") == "tool_result"
                for b in content
            )
            # 纯 tool_result 消息不算用户消息
            if has_tool_result and not has_text:
                return True

            # 检查文本内容是否为系统消息
            if has_text:
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text.startswith("<") or text.startswith("[Request interrupted"):
                            return True

        return False

    def _parse_single_message(
        self, data: dict[str, Any], msg_type: str
    ) -> Message | None:
        """解析单条消息"""
        uuid = data.get("uuid", "")
        timestamp_str = data.get("timestamp", "")
        model = data.get("message", {}).get("model")

        # 解析时间戳
        timestamp = None
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(
                    timestamp_str.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        # 解析内容
        content_blocks = self._parse_content(data.get("message", {}))

        if not content_blocks:
            return None

        # 判断真实角色：
        # - type=user 且只有 tool_result 块 → 这是工具返回值，不是用户消息
        # - type=user 且有 text 块 → 真实用户消息
        # - type=assistant → 助手消息
        role = self._determine_role(msg_type, content_blocks)

        return Message(
            id=uuid,
            role=role,
            content=content_blocks,
            timestamp=timestamp,
            model=model,
        )

    @staticmethod
    def _determine_role(msg_type: str, blocks: list[ContentBlock]) -> MessageRole:
        """根据消息类型和内容块判断真实角色"""
        if msg_type == "assistant":
            return MessageRole.ASSISTANT

        if msg_type == "user":
            # 检查是否全部是 tool_result
            has_text = any(b.type == ContentBlockType.TEXT for b in blocks)
            has_tool_result = any(b.type == ContentBlockType.TOOL_RESULT for b in blocks)

            # 纯 tool_result 消息 → 工具角色
            if has_tool_result and not has_text:
                return MessageRole.TOOL

            # 有 text 内容 → 用户角色
            return MessageRole.USER

        return MessageRole.USER

    def _parse_content(self, message: dict[str, Any]) -> list[ContentBlock]:
        """解析消息内容"""
        blocks = []
        content = message.get("content", "")

        # 简单字符串内容
        if isinstance(content, str):
            if content.strip():
                blocks.append(
                    ContentBlock(type=ContentBlockType.TEXT, content=content)
                )
            return blocks

        # 数组内容（包含多种类型）
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue

                item_type = item.get("type", "")

                if item_type == "text":
                    text = item.get("text", "")
                    if text.strip():
                        blocks.append(
                            ContentBlock(
                                type=ContentBlockType.TEXT, content=text
                            )
                        )

                elif item_type == "thinking":
                    thinking = item.get("thinking", "")
                    if thinking.strip():
                        blocks.append(
                            ContentBlock(
                                type=ContentBlockType.THINKING,
                                content=thinking,
                            )
                        )

                elif item_type == "tool_use":
                    tool_name = item.get("name", "unknown")
                    tool_input = item.get("input", {})
                    blocks.append(
                        ContentBlock(
                            type=ContentBlockType.TOOL_USE,
                            content=json.dumps(tool_input, ensure_ascii=False, indent=2),
                            metadata={"tool_name": tool_name},
                        )
                    )

                elif item_type == "tool_result":
                    result_content = item.get("content", "")
                    is_error = item.get("is_error", False)
                    if isinstance(result_content, list):
                        result_content = json.dumps(
                            result_content, ensure_ascii=False
                        )
                    blocks.append(
                        ContentBlock(
                            type=ContentBlockType.TOOL_RESULT,
                            content=str(result_content),
                            metadata={"is_error": is_error},
                        )
                    )

        return blocks

    @staticmethod
    def iterdir_safe(path: Path):
        """安全地遍历目录"""
        try:
            return list(path.iterdir())
        except (PermissionError, OSError):
            return []
