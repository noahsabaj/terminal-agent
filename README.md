# Terminal Agent

A coding agent for the terminal, powered by Ollama Cloud.

**Always runs sandboxed in Podman for safety.**

![Terminal Agent](https://img.shields.io/badge/version-0.1-green)
![Sandboxed](https://img.shields.io/badge/sandboxed-always-blue)

## Install

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/noahsabaj/terminal-agent/main/install.sh | bash
```

**Windows:** Coming soon.

Requires [Podman](https://podman.io/docs/installation). On macOS, run `podman machine init && podman machine start` first.

## Usage

```bash
agent              # Start the agent
agent --yolo       # Autonomous mode (no permission prompts)
```

## Features

- **7 Tools**: read_file, list_files, write_file, edit_file, run_bash, web_search, web_fetch
- **Always Sandboxed**: Runs in Podman container - Ctrl+C kills everything safely
- **Pretty Output**: Syntax highlighting, markdown tables with box-drawing characters
- **Smart Editing**: Requires unique text matches to prevent accidental edits
- **Dynamic Bash**: Configurable timeout and output truncation
- **Security**: Dangerous command blocklist that cannot be bypassed

## Commands

Inside the agent:

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/model <name>` | Switch model |
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

- **Always sandboxed** - Runs in Podman, can only access current directory
- **Dangerous commands blocked** - `rm -rf /`, fork bombs, etc. blocked even in yolo mode
- **Ctrl+C = full stop** - Kills container and all processes instantly

## Uninstall

```bash
rm -rf ~/.terminal-agent ~/.local/bin/agent
podman rmi terminal-agent 2>/dev/null
```

## License

Dual-licensed under [MIT](LICENSE-MIT) or [Apache 2.0](LICENSE-APACHE), at your option.
