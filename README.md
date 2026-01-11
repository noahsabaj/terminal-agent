# Terminal Agent

A coding agent for the terminal, powered by Ollama Cloud + MiniMax-M2.1.

**Always runs sandboxed in a Podman container for safety.**

![Terminal Agent](https://img.shields.io/badge/version-0.1-green)
![Sandboxed](https://img.shields.io/badge/sandboxed-always-blue)

## Features

- **7 Tools**: read_file, list_files, write_file, edit_file, run_bash, web_search, web_fetch
- **Always Sandboxed**: Runs in Podman container by default - Ctrl+C kills everything safely
- **Pretty Output**: Syntax highlighting, beautiful markdown tables with box-drawing characters
- **Smart Editing**: Requires unique text matches to prevent accidental edits
- **Dynamic Bash**: Configurable timeout and output truncation (first/last/both/all)
- **Security**: Dangerous command blocklist (active even in yolo mode), malicious code detection
- **Global Command**: Run `agent` from any directory
- **YOLO Mode**: `--yolo` flag for autonomous operation (no permission prompts)

## Requirements

- Python 3.10+
- **Podman** (required - sandbox is mandatory)
- Ollama Cloud account

## Installation

```bash
# Clone the repo
git clone https://github.com/noahsabaj/terminal-agent.git
cd terminal-agent

# Install the global command
mkdir -p ~/.local/bin
cat > ~/.local/bin/agent << 'EOF'
#!/bin/bash
set -e
IMAGE_NAME="terminal-agent"
AGENT_DIR="$HOME/terminal-agent"  # Adjust this path

if ! podman image exists "$IMAGE_NAME" 2>/dev/null; then
    echo "Setting up Terminal Agent (first run only)..."
    podman build -t "$IMAGE_NAME" -f "$AGENT_DIR/Containerfile" "$AGENT_DIR" > /dev/null 2>&1
fi

exec podman run --rm -it \
    -v "$(pwd):/workspace/project:Z" \
    --workdir /workspace/project \
    --tmpfs /tmp \
    --security-opt=no-new-privileges \
    --hostname terminal-agent \
    -e TERM="$TERM" \
    "$IMAGE_NAME" "$@"
EOF
chmod +x ~/.local/bin/agent

# Add to PATH (if not already)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Build the container (first run does this automatically)
podman build -t terminal-agent .
```

## Usage

```bash
# Navigate to any project and start the agent
cd ~/my-project
agent

# Start in YOLO mode (no permission prompts)
agent --yolo

# Use a different model
agent --model deepseek-v3.1:671b-cloud
```

## How Sandboxing Works

When you run `agent`, it:

1. Starts a Podman container
2. Mounts your **current directory** into the container
3. The agent can only access files in that directory
4. Ctrl+C kills the container and all processes inside
5. Container is removed automatically on exit

You never interact with Podman directly - it's invisible.

## Commands

Inside the agent:
- `/help` - Show available commands
- `/model <name>` - Switch model
- `/clear` - Clear conversation history
- `/tokens` - Show token usage
- `/quit` - Exit

## Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents |
| `list_files` | List directory contents |
| `write_file` | Create new files |
| `edit_file` | Edit existing files (requires unique match) |
| `run_bash` | Execute shell commands (with timeout & output control) |
| `web_search` | Search the web |
| `web_fetch` | Fetch content from a URL |

## Security

- **Always sandboxed** - Runs in Podman container, can only access current directory
- **Dangerous commands blocked**: `rm -rf /`, fork bombs, disk wiping, etc.
- **Blocked even in YOLO mode** - Hardcoded protection that cannot be bypassed
- **Malicious code detection** - Model is instructed to detect and warn about suspicious code
- **Ctrl+C = full stop** - Kills container and all processes instantly

## License

Dual-licensed under [MIT](LICENSE) or [Apache 2.0](LICENSE), at your option.
