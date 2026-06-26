# Agent Chat Hub

<div align="center">

**🤖 统一查看你的 AI Agent 聊天记录**

*CLI Agent 的聊天记录，像网页版一样好看*

[English](#english-version) | 中文

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-brightgreen.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)

</div>

---

## 🎯 这是什么？

你是否经常使用 Claude Code、Codex CLI 等命令行 AI Agent 工具？  
你是否厌倦了在终端里滚动翻找之前的对话？  
你是否希望能像 ChatGPT 网页版那样，美观地浏览所有聊天记录？

**Agent Chat Hub** 就是为此而生！

它能自动检测你本地所有 AI Agent 的聊天记录，以美观的 Web 界面统一展示，让你像浏览网页一样查看所有对话。

## ✨ 核心亮点

### 🚀 一键启动，开箱即用
```bash
# Windows: 双击 start.bat
# macOS/Linux: ./start.sh
```
无需复杂配置，自动安装依赖，自动打开浏览器。

### 🔍 自动检测，智能识别
自动扫描本地已安装的 Agent 工具，无需手动指定路径：
- ✅ Claude Code
- ✅ Codex CLI  
- ✅ OpenCode 及其衍生版本

### 🎨 美观界面，舒适体验
- 深色主题，护眼舒适
- 用户问题靠右，AI 回答靠左，清晰区分
- 代码高亮，Markdown 完整渲染
- 思考过程、工具调用默认折叠，点击展开

### 📁 目录树，一目了然
按项目目录自动归类会话，层级分明：
```
💾 D:
  📁 PycharmProject
    📁 MyProject
      🟠 帮我分析这段代码...
      🟠 如何优化性能...
    📁 AnotherProject
      🔵 解释这个函数...
```

### ↔️ 可调侧边栏
拖动分隔线自由调整侧边栏宽度，长标题不再被截断。

## 📸 界面预览

```
┌─────────────────────────────────────────────────────────────────┐
│  💾 D:                              我的项目问题               │
│    📁 PycharmProject                                            │
│      📁 MyProject                     👤 用户                  │
│        🟠 帮我分析这段代码          ─────────────────────      │
│        🟠 如何优化性能              帮我分析这段代码的性能...   │
│      📁 AnotherProject                                         │
│        🔵 解释这个函数                🤖 助手                  │
│                                   ─────────────────────        │
│  💾 C:                              好的，我来分析这段代码...  │
│    📁 Users                                                  │
│      📁 .claude                                             │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 方式一：一键启动（推荐）

**Windows:**
```bash
git clone https://github.com/litangdingzhen12138/agent-chat-hub.git
cd agent-chat-hub
start.bat
```

**macOS / Linux:**
```bash
git clone https://github.com/litangdingzhen12138/agent-chat-hub.git
cd agent-chat-hub
chmod +x start.sh
./start.sh
```

### 方式二：手动启动

```bash
# 克隆项目
git clone https://github.com/litangdingzhen12138/agent-chat-hub.git
cd agent-chat-hub

# 安装依赖
pip install -r requirements.txt

# 启动服务
python -m app.main
```

启动后浏览器自动打开 `http://localhost:8765`

### 停止服务

在运行服务的终端中按 `Ctrl+C` 即可停止。

如果已关闭终端但服务仍在后台运行：

**Windows:**
```bash
taskkill //F //IM python.exe
```

**macOS / Linux:**
```bash
pkill -f "python -m app.main"
```

或在任务管理器（Windows）/ 活动监视器（macOS）中结束 **python** 进程。

## 📂 支持的 Agent 工具


| 工具 | 数据位置 | 颜色 | 自动检测 |
|------|----------|------|----------|
| 🟠 **Claude Code** | `~/.claude/projects/` | 橙色 | ✅ |
| 🔵 **Codex CLI** | `~/.codex/sessions/` + `history.jsonl` | 蓝色 | ✅ |
| 🟢 **OpenCode** | `~/.local/share/opencode/` | 绿色 | ✅ |
| 🟣 **agent1** | `~/.local/share/deveco/` | 紫色 | ✅ |
| 💗 **agent2** | `~/.local/share/codeagent/` | 粉色 | ✅ |
| 🩵 **其他衍生版** | `~/.local/share/<名称>/` | 自动分配 | ✅ |


> 💡 所有基于 OpenCode 的衍生工具都会被自动识别，无需额外配置。每个 Agent 有独立的颜色标识，便于区分。

## 🛠️ 功能特性

| 功能 | 说明 |
|------|------|
| 🔍 自动检测 | 自动扫描本地 Agent 数据，无需手动配置 |
| 📁 目录树 | 按项目目录层级组织会话，清晰直观 |
| 💬 聊天气泡 | 用户问题靠右，AI 回答靠左 |
| 📝 Markdown | 完整渲染，代码语法高亮 |
| 🔧 工具调用 | 折叠展示 AI 的工具调用过程 |
| 💭 思考过程 | 可折叠查看 AI 的思考过程 |
| 🔎 全文搜索 | 跨会话搜索消息内容 |
| 📤 文件上传 | 支持上传单个文件或整个文件夹 |
| ↔️ 可调宽度 | 拖动调整侧边栏宽度 |
| 📂 折叠/展开 | 一键折叠或展开所有目录 |

## ⚙️ 配置

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `PORT` | 服务端口 | 自动查找 (8765-8799) |

### 示例

```bash
# 指定端口启动
PORT=9000 python -m app.main
```

## 🛠️ 技术栈

- **后端**: Python + FastAPI
- **前端**: HTML + Tailwind CSS + Marked.js + Highlight.js
- **存储**: 支持 JSONL、SQLite 等多种格式
- **特点**: 纯 Python 运行，无需 Node.js 环境

## 📁 项目结构

```
agent-chat-hub/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 入口
│   ├── detector.py           # 自动检测
│   ├── models.py             # 数据模型
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── base.py           # 解析器基类
│   │   ├── claude_code.py    # Claude Code 解析器
│   │   ├── opencode.py       # OpenCode 解析器
│   └── static/
│       └── index.html        # 前端页面
├── requirements.txt
├── start.bat                 # Windows 启动脚本
├── start.sh                  # Linux/Mac 启动脚本
├── LICENSE
└── README.md
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 添加新的 Agent 支持

如果你想添加对新 Agent 工具的支持：

1. 在 `app/parsers/` 目录下创建新的解析器
2. 继承 `BaseParser` 基类
3. 在 `app/detector.py` 中添加检测逻辑
4. 在 `app/main.py` 中注册新的解析器

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

<a name="english-version"></a>

## English Version

### What is Agent Chat Hub?

**Agent Chat Hub** is a beautiful web-based viewer for AI Agent CLI chat histories. It automatically detects and displays chat records from tools like Claude Code, Codex CLI, and OpenCode in a unified, easy-to-browse interface.

### Why Agent Chat Hub?

If you frequently use command-line AI Agent tools but miss the clean chat interface of web-based AI assistants, Agent Chat Hub is for you. It transforms your local chat logs into a beautiful web experience.

### Key Features

- **One-Click Launch** - Double-click `start.bat` (Windows) or run `./start.sh` (macOS/Linux)
- **Auto-Detection** - Automatically finds all your Agent chat histories
- **Beautiful UI** - Dark theme, chat bubbles, code highlighting
- **Directory Tree** - Organized by project structure
- **Universal Support** - Claude Code, Codex CLI, OpenCode and derivatives

### Quick Start

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/agent-chat-hub.git
cd agent-chat-hub

# Windows
start.bat

# macOS / Linux
chmod +x start.sh
./start.sh
```

The browser will automatically open at `http://localhost:8765`.

### Supported Tools

| Tool | Data Location | Auto-Detect |
|------|---------------|-------------|
| 🟠 Claude Code | `~/.claude/projects/` | ✅ |
| 🔵 Codex CLI | `~/.codex/sessions/` | ✅ |
| 🟢 OpenCode | `~/.local/share/opencode/` | ✅ |

### Tech Stack

- **Backend**: Python + FastAPI
- **Frontend**: HTML + Tailwind CSS + Marked.js + Highlight.js
- **No Node.js Required** - Pure Python implementation

### License

MIT License

---

## 📋 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)

---

<div align="center">

**如果这个项目对你有帮助，请给个 ⭐ Star 支持一下！**

</div>
