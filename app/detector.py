"""自动检测各 Agent CLI 工具的数据路径"""

from __future__ import annotations

import os
from pathlib import Path

from .models import Source, SourceType


def get_home_dir() -> Path:
    """获取用户主目录"""
    return Path.home()


def detect_claude_code() -> Source:
    """检测 Claude Code 数据"""
    home = get_home_dir()
    claude_dir = home / ".claude" / "projects"

    if claude_dir.exists():
        # 统计会话数量
        session_count = 0
        for project_dir in claude_dir.iterdir():
            if project_dir.is_dir():
                for f in project_dir.iterdir():
                    if f.suffix == ".jsonl" and f.is_file():
                        session_count += 1

        return Source(
            id=SourceType.CLAUDE_CODE,
            name="Claude Code",
            available=session_count > 0,
            path=str(claude_dir),
            session_count=session_count,
        )

    return Source(
        id=SourceType.CLAUDE_CODE,
        name="Claude Code",
        available=False,
        path=str(claude_dir),
    )


def detect_opencode() -> Source:
    """检测 OpenCode 数据（包括所有类 OpenCode 的 agent）"""
    home = get_home_dir()

    # 扫描 ~/.local/share/ 下所有子目录
    data_dir = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))

    if data_dir.exists():
        for subdir in sorted(data_dir.iterdir()):
            if not subdir.is_dir():
                continue

            agent_name = subdir.name

            # opencode 目录：优先检查 opencode.db
            if agent_name == "opencode":
                db_file = subdir / "opencode.db"
                if db_file.exists():
                    session_count = _count_opencode_sessions(db_file)
                    if session_count > 0:
                        return Source(
                            id=SourceType.OPENCODE,
                            name=agent_name,
                            available=True,
                            path=str(db_file),
                            session_count=session_count,
                        )

            # 其他目录：扫描所有 .db 文件
            else:
                for db_file in subdir.glob("*.db"):
                    session_count = _count_opencode_sessions(db_file)
                    if session_count > 0:
                        return Source(
                            id=SourceType.OPENCODE,
                            name=agent_name,
                            available=True,
                            path=str(db_file),
                            session_count=session_count,
                        )

    # 检查 XDG_CONFIG_HOME
    config_dir = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    if config_dir.exists():
        for subdir in sorted(config_dir.iterdir()):
            if not subdir.is_dir():
                continue
            for db_file in subdir.glob("*.db"):
                session_count = _count_opencode_sessions(db_file)
                if session_count > 0:
                    return Source(
                        id=SourceType.OPENCODE,
                        name=subdir.name,
                        available=True,
                        path=str(db_file),
                        session_count=session_count,
                    )

    # 检查 ~/.<name>/ 格式
    for pattern in ["opencode", "codeagent", "deveco"]:
        db_file = home / f".{pattern}" / "opencode.db"
        if db_file.exists():
            session_count = _count_opencode_sessions(db_file)
            if session_count > 0:
                return Source(
                    id=SourceType.OPENCODE,
                    name=pattern,
                    available=True,
                    path=str(db_file),
                    session_count=session_count,
                )

    # 检查当前目录
    cwd = Path.cwd()
    local_db = cwd / ".opencode" / "opencode.db"
    if local_db.exists():
        session_count = _count_opencode_sessions(local_db)
        if session_count > 0:
            return Source(
                id=SourceType.OPENCODE,
                name="opencode",
                available=True,
                path=str(local_db),
                session_count=session_count,
            )

    return Source(
        id=SourceType.OPENCODE,
        name="opencode",
        available=False,
        path=str(home / ".local" / "share" / "opencode" / "opencode.db"),
    )


def _count_opencode_sessions(db_path: Path) -> int:
    """统计 OpenCode 数据库中的会话数量"""
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        # OpenCode 实际使用 session 表（不是 sessions）
        cursor = conn.execute(
            "SELECT COUNT(*) FROM session WHERE parent_id IS NULL"
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def detect_codex_cli() -> Source:
    """检测 Codex-CLI 数据"""
    home = get_home_dir()
    codex_dir = home / ".codex"
    history_file = codex_dir / "history.jsonl"
    sessions_dir = codex_dir / "sessions"

    # 统计 rollout 文件数量
    rollout_count = 0
    if sessions_dir.exists():
        for _ in sessions_dir.rglob("rollout-*.jsonl"):
            rollout_count += 1

    # 统计 history.jsonl 中的独立会话数
    history_session_count = 0
    if history_file.exists():
        try:
            session_ids = set()
            with open(history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        import json
                        data = json.loads(line)
                        sid = data.get("session_id", "")
                        if sid:
                            session_ids.add(sid)
                    except Exception:
                        continue
            history_session_count = len(session_ids)
        except Exception:
            pass

    total_count = rollout_count + history_session_count
    available = total_count > 0

    return Source(
        id=SourceType.CODEX_CLI,
        name="Codex CLI",
        available=available,
        path=str(codex_dir),
        session_count=total_count,
    )


def detect_all() -> list[Source]:
    """检测所有支持的数据源"""
    return [
        detect_claude_code(),
        detect_opencode(),
        detect_codex_cli(),
    ]


def get_source_by_id(source_id: str) -> Source | None:
    """根据 ID 获取数据源"""
    detectors = {
        SourceType.CLAUDE_CODE: detect_claude_code,
        SourceType.OPENCODE: detect_opencode,
        SourceType.CODEX_CLI: detect_codex_cli,
    }

    try:
        source_type = SourceType(source_id)
    except ValueError:
        return None

    detector = detectors.get(source_type)
    if detector:
        return detector()
    return None
