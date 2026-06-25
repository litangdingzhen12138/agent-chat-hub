"""Agent Chat Visualizer - FastAPI 主应用"""

from __future__ import annotations

import os
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .detector import detect_all, get_source_by_id
from .models import Source, SourceType
from .parsers.claude_code import ClaudeCodeParser
from .parsers.codex_cli import CodexCliParser
from .parsers.opencode import OpenCodeParser


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时自动打开浏览器
    webbrowser.open(f"http://localhost:{_actual_port}")
    yield


app = FastAPI(
    title="Agent Chat Hub",
    description="统一查看 AI Agent CLI 聊天记录 - Claude Code、Codex CLI、OpenCode",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件目录
STATIC_DIR = Path(__file__).parent / "static"

# 实际运行端口（在启动时设置）
_actual_port = 8765

# 上传文件临时目录
UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# 解析器缓存
_parsers: dict[str, object] = {}


def _get_parser(source_id: str):
    """获取或创建解析器"""
    if source_id in _parsers:
        return _parsers[source_id]

    source = get_source_by_id(source_id)
    if not source or not source.available:
        return None

    parser = None
    if source_id == SourceType.CLAUDE_CODE:
        parser = ClaudeCodeParser(source.path)
    elif source_id == SourceType.OPENCODE:
        parser = OpenCodeParser(source.path)
    elif source_id == SourceType.CODEX_CLI:
        parser = CodexCliParser(source.path)

    if parser:
        _parsers[source_id] = parser

    return parser


# ============ API 路由 ============


@app.get("/api/sources")
async def list_sources():
    """列出所有可用的数据源"""
    sources = detect_all()
    return {"sources": [s.model_dump() for s in sources]}


@app.get("/api/sessions")
async def list_sessions(source: Optional[str] = None, grouped: bool = False):
    """列出所有会话，可按数据源过滤"""
    all_sessions = []

    sources_to_check = [source] if source else [s.value for s in SourceType]

    for source_id in sources_to_check:
        parser = _get_parser(source_id)
        if parser:
            sessions = parser.get_sessions()
            all_sessions.extend(s.model_dump() for s in sessions)

    # 按创建时间排序
    all_sessions.sort(
        key=lambda s: s.get("created_at") or "", reverse=True
    )

    # 按目录分组
    if grouped:
        groups: dict[str, list] = {}
        for s in all_sessions:
            project_path = s.get("metadata", {}).get("project_path", "未知目录")
            if project_path not in groups:
                groups[project_path] = []
            groups[project_path].append(s)

        # 转换为列表格式
        grouped_sessions = []
        for path, sessions in sorted(groups.items()):
            grouped_sessions.append({
                "directory": path,
                "sessions": sessions,
                "count": len(sessions),
            })

        return {"groups": grouped_sessions, "total": len(all_sessions)}

    return {"sessions": all_sessions}


@app.get("/api/sessions/{source_id}/{session_id}/messages")
async def get_session_messages(source_id: str, session_id: str):
    """获取指定会话的所有消息"""
    parser = _get_parser(source_id)
    if not parser:
        raise HTTPException(status_code=404, detail=f"数据源不可用: {source_id}")

    messages = parser.get_messages(session_id)
    return {"messages": [m.model_dump() for m in messages]}


@app.get("/api/search")
async def search_messages(q: str, source: Optional[str] = None):
    """搜索消息内容"""
    if not q.strip():
        return {"results": []}

    all_results = []

    sources_to_check = [source] if source else [s.value for s in SourceType]

    for source_id in sources_to_check:
        parser = _get_parser(source_id)
        if parser:
            results = parser.search(q)
            all_results.extend(results)

    return {"results": all_results}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """手动上传聊天记录文件"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")

    # 检查文件类型
    filename = file.filename.lower()
    if not (filename.endswith(".jsonl") or filename.endswith(".json") or filename.endswith(".db")):
        raise HTTPException(
            status_code=400,
            detail="不支持的文件类型，请上传 .jsonl、.json 或 .db 文件",
        )

    # 保存文件到上传目录
    file_path = UPLOAD_DIR / file.filename
    content = await file.read()

    with open(file_path, "wb") as f:
        f.write(content)

    # 识别文件类型
    source_id = _detect_upload_type(file_path)

    # 清除解析器缓存，强制重新加载
    _parsers.clear()

    # 如果是 Codex rollout 文件，复制到 sessions 目录
    if source_id == SourceType.CODEX_CLI and "rollout-" in file.filename:
        import shutil
        from datetime import datetime
        now = datetime.now()
        dest_dir = Path.home() / ".codex" / "sessions" / str(now.year) / f"{now.month:02d}" / f"{now.day:02d}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / file.filename
        shutil.copy2(file_path, dest_path)

    return {
        "success": True,
        "filename": file.filename,
        "path": str(file_path),
        "detected_type": source_id,
        "message": "文件上传成功",
    }


def _detect_upload_type(file_path: Path) -> str:
    """检测上传文件的类型，只有包含有效会话数据才返回对应类型"""
    if file_path.suffix == ".db":
        # 检查是否为 OpenCode 类数据库
        if _is_opencode_db(file_path):
            return SourceType.OPENCODE
        return SourceType.UNKNOWN

    if file_path.suffix in (".jsonl", ".json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i > 10:  # 检查前10行
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = __import__("json").loads(line)
                        # Codex rollout 格式
                        if data.get("type") == "session_meta" and "payload" in data:
                            return SourceType.CODEX_CLI
                        # Codex history 格式
                        if "session_id" in data and "ts" in data:
                            return SourceType.CODEX_CLI
                        # Claude Code 格式
                        if "type" in data and "message" in data:
                            return SourceType.CLAUDE_CODE
                    except Exception:
                        continue
        except Exception:
            pass

    return SourceType.UNKNOWN


def _is_opencode_db(db_path: Path) -> bool:
    """检查 .db 文件是否为 OpenCode 类会话数据库"""
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        # 检查是否有 session 表且有数据
        cursor = conn.execute(
            "SELECT COUNT(*) FROM session WHERE parent_id IS NULL"
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False


# ============ 前端路由 ============


@app.get("/")
async def serve_index():
    """提供前端页面"""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")
    return HTMLResponse("<h1>Agent Chat Visualizer</h1><p>前端文件未找到</p>")


def find_available_port(start_port: int = 8765, max_port: int = 8799) -> int:
    """查找可用端口"""
    import socket
    for port in range(start_port, max_port + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    return start_port  # 如果都不可用，返回起始端口让 uvicorn 报错


def main():
    """主函数 - 启动服务"""
    global _actual_port
    import uvicorn

    port = int(os.environ.get("PORT", "0"))
    if port == 0:
        port = find_available_port()

    _actual_port = port

    print(f"\n{'='*50}")
    print(f"  Agent Chat Hub")
    print(f"  统一查看 AI Agent 聊天记录")
    print(f"  访问地址: http://localhost:{port}")
    print(f"{'='*50}\n")

    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
