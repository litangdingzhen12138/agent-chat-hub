"""解析器基类"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Message, Session, Source


class BaseParser(ABC):
    """Agent CLI 聊天记录解析器基类"""

    @abstractmethod
    def get_sessions(self) -> list[Session]:
        """获取所有会话列表"""
        ...

    @abstractmethod
    def get_messages(self, session_id: str) -> list[Message]:
        """获取指定会话的所有消息"""
        ...

    @abstractmethod
    def search(self, query: str) -> list[dict]:
        """搜索消息内容"""
        ...

    @abstractmethod
    def get_source(self) -> Source:
        """获取数据源信息"""
        ...
