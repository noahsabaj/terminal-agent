# Terminal Agent

A coding agent for the terminal, powered by Ollama Cloud.

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue)

## Install

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/noahsabaj/open-terminal-agent/main/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/noahsabaj/open-terminal-agent/main/install.ps1 | iex
```

### Requirements

- Python 3.10+
- [Ollama](https://ollama.com) - works with both local and cloud models
  - **Local models**: `ollama pull llama3:8b` then `terminal-agent -m llama3:8b`
  - **Cloud models**: `ollama signin` for access to cloud models (default)

## Usage

```bash
terminal-agent                # Start normally (prompts for permission)
terminal-agent --accept-edits # Auto-approve file edits, prompt for bash
terminal-agent --yolo         # Full autonomous mode (no prompts)
```

## Features

- **7 Tools**: read_file, list_files, write_file, edit_file, run_bash, web_search, web_fetch
- **Permission Prompts**: Asks before writing files or running commands
- **Pretty Output**: Syntax highlighting, markdown tables with box-drawing characters
- **Smart Editing**: Requires unique text matches to prevent accidental edits
- **Dynamic Bash**: Configurable timeout and output truncation

## Commands

Inside the agent:

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/mode` | Cycle permission mode (default → accept-edits → yolo) |
| `/model <name>` | Switch model (local or cloud) |
| `/clear` | Clear conversation history |
| `/tokens` | Show token usage |
| `/quit` | Exit |

## Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents |
| `list_files` | List directory contents |
| `write_file` | Create new files |
| `edit_file` | Edit existing files (requires unique match) |
| `run_bash` | Execute shell commands |
| `web_search` | Search the web |
| `web_fetch` | Fetch content from a URL |

## Security

- **Permission prompts** - Asks before writing files or running commands (default)
- **Dangerous commands blocked** - `rm -rf /`, fork bombs, etc. blocked in all modes
- **Ctrl+C = stop** - Interrupts the agent immediately

### Permission Modes

| Mode | Description |
|------|-------------|
| Default | Prompts for file writes and bash commands |
| `--accept-edits` | Auto-approves file edits, prompts for bash |
| `--yolo` | Full autonomous mode (use with caution) |

## Uninstall

```bash
rm -rf ~/.terminal-agent ~/.local/bin/terminal-agent
```

## License

Dual-licensed under [MIT](LICENSE-MIT) or [Apache 2.0](LICENSE-APACHE), at your option.
