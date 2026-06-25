"""数据模型定义 - Agent Chat Visualizer"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """支持的 Agent CLI 工具类型"""
    CLAUDE_CODE = "claude-code"
    OPENCODE = "opencode"
    CODEX_CLI = "codex-cli"
    UNKNOWN = "unknown"


class ContentBlockType(str, Enum):
    """消息内容块类型"""
    TEXT = "text"
    THINKING = "thinking"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    CODE = "code"
    ERROR = "error"


class ContentBlock(BaseModel):
    """消息内容块"""
    type: ContentBlockType
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class MessageRole(str, Enum):
    """消息角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Message(BaseModel):
    """聊天消息"""
    id: str
    role: MessageRole
    content: list[ContentBlock] = Field(default_factory=list)
    timestamp: Optional[datetime] = None
    model: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Session(BaseModel):
    """聊天会话"""
    id: str
    source: SourceType
    title: str = ""
    message_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Source(BaseModel):
    """数据源"""
    id: SourceType
    name: str
    available: bool = False
    path: str = ""
    session_count: int = 0


class SearchResult(BaseModel):
    """搜索结果"""
    session_id: str
    session_title: str
    message_id: str
    message_role: MessageRole
    matched_text: str
    timestamp: Optional[datetime] = None
