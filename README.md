# Terminal Agent

A coding agent for the terminal, powered by Ollama Cloud + MiniMax-M2.1.

![Terminal Agent](https://img.shields.io/badge/version-0.1-green)

## Features

- **7 Tools**: read_file, list_files, write_file, edit_file, run_bash, web_search, web_fetch
- **Pretty Output**: Syntax highlighting, beautiful markdown tables with box-drawing characters
- **Smart Editing**: Requires unique text matches to prevent accidental edits
- **Dynamic Bash**: Configurable timeout and output truncation (first/last/both/all)
- **Security**: Dangerous command blocklist, malicious code detection
- **Global Command**: Run `agent` from any directory
- **YOLO Mode**: `--yolo` flag for full autonomous operation

## Installation

```bash
# Clone the repo
git clone https://github.com/noahsabaj/terminal-agent.git
cd terminal-agent

# Install dependencies
pip install -r requirements.txt

# Make it globally available
mkdir -p ~/.local/bin
cp agent.py ~/.local/bin/
cat > ~/.local/bin/agent << 'EOF'
#!/usr/bin/env python3
import os, sys
AGENT_PATH = os.path.expanduser("~/.local/bin/agent.py")
os.execv(sys.executable, [sys.executable, AGENT_PATH] + sys.argv[1:])
EOF
chmod +x ~/.local/bin/agent

# Add to PATH (if not already)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## Usage

```bash
# Start the agent
agent

# Start in YOLO mode (no permission prompts)
agent --yolo

# Use a different model
agent --model deepseek-v3.1:671b-cloud
```

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

- **Dangerous commands blocked**: `rm -rf /`, fork bombs, disk wiping, etc.
- **Blocked even in YOLO mode** - hardcoded protection
- **Malicious code detection** in the system prompt
- **Optional Podman sandbox** for full isolation

## Sandboxed Mode (Optional)

Run in a Podman container for maximum safety:

```bash
./run-sandboxed.sh /path/to/your/project
```

## Requirements

- Python 3.10+
- Ollama Cloud account
- `rich` and `pygments` for terminal output

## License

MIT
