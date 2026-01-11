#!/bin/bash
# Terminal Agent - One-line installer
# curl -fsSL https://raw.githubusercontent.com/noahsabaj/terminal-agent/main/install.sh | bash

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
echo "  ╭─────╮"
echo "  │ ◠ ◠ │   Terminal Agent Installer"
echo "  │  ▽  │"
echo "  ╰─────╯"
echo -e "${NC}"

# Detect OS
OS="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
fi

# Check for podman
if ! command -v podman &> /dev/null; then
    echo -e "${RED}Error: Podman is required but not installed.${NC}"
    echo ""
    echo "Install Podman first:"
    echo "  Ubuntu/Debian: sudo apt install podman"
    echo "  Fedora:        sudo dnf install podman"
    echo "  Arch:          sudo pacman -S podman"
    echo "  macOS:         brew install podman"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓${NC} Podman found"

# macOS: Check if podman machine is running
if [[ "$OS" == "macos" ]]; then
    if ! podman machine inspect &> /dev/null; then
        echo -e "${YELLOW}!${NC} Podman machine not initialized"
        echo -e "  Initializing podman machine..."
        podman machine init
    fi

    if ! podman machine inspect --format '{{.State}}' 2>/dev/null | grep -q "running"; then
        echo -e "${YELLOW}!${NC} Starting podman machine..."
        podman machine start
    fi

    echo -e "${GREEN}✓${NC} Podman machine running"
fi

# Check for ollama
if ! command -v ollama &> /dev/null; then
    if [[ "$OS" == "linux" ]]; then
        echo -e "${YELLOW}!${NC} Ollama not found - installing..."
        curl -fsSL https://ollama.com/install.sh | sh
        echo -e "${GREEN}✓${NC} Ollama installed"
    else
        echo -e "${RED}!${NC} Ollama not found"
        echo ""
        echo "  Download Ollama from: ${CYAN}https://ollama.com/download${NC}"
        echo "  Install the .dmg, then run this script again."
        echo ""
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} Ollama found"
fi

# Check if user needs to sign in to Ollama (for cloud models)
echo ""
echo -e "${YELLOW}!${NC} Terminal Agent uses cloud models (e.g., minimax-m2.1:cloud)"
echo -e "  If you haven't already, sign in to Ollama:"
echo ""
echo -e "  ${CYAN}ollama signin${NC}"
echo ""
read -p "Press Enter to continue (or Ctrl+C to sign in first)..."
echo ""

# Create directories
INSTALL_DIR="$HOME/.terminal-agent"
BIN_DIR="$HOME/.local/bin"

mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

echo -e "${GREEN}✓${NC} Created directories"

# Download files from GitHub
REPO_URL="https://raw.githubusercontent.com/noahsabaj/terminal-agent/main"

echo -e "${YELLOW}↓${NC} Downloading agent.py..."
curl -fsSL "$REPO_URL/agent.py" -o "$INSTALL_DIR/agent.py"

echo -e "${YELLOW}↓${NC} Downloading Containerfile..."
curl -fsSL "$REPO_URL/Containerfile" -o "$INSTALL_DIR/Containerfile"

echo -e "${YELLOW}↓${NC} Downloading requirements.txt..."
curl -fsSL "$REPO_URL/requirements.txt" -o "$INSTALL_DIR/requirements.txt"

echo -e "${GREEN}✓${NC} Downloaded all files"

# Create the agent wrapper script
cat > "$BIN_DIR/agent" << 'WRAPPER'
#!/bin/bash
# Terminal Agent - Sandboxed in Podman (transparent to user)

set -e

IMAGE_NAME="terminal-agent"
AGENT_DIR="$HOME/.terminal-agent"

# Build image if it doesn't exist (first run only)
if ! podman image exists "$IMAGE_NAME" 2>/dev/null; then
    echo "Setting up Terminal Agent (first run only)..."
    podman build -t "$IMAGE_NAME" -f "$AGENT_DIR/Containerfile" "$AGENT_DIR" 2>&1 | while read line; do
        echo -ne "\r\033[K  $line"
    done
    echo -e "\r\033[K\033[32m✓\033[0m Container ready"
    echo ""
fi

# Run sandboxed (--network=host allows access to Ollama on host)
exec podman run --rm -it \
    -v "$(pwd):/workspace/project:Z" \
    --workdir /workspace/project \
    --tmpfs /tmp \
    --security-opt=no-new-privileges \
    --hostname terminal-agent \
    --network=host \
    -e TERM="$TERM" \
    "$IMAGE_NAME" "$@"
WRAPPER

chmod +x "$BIN_DIR/agent"

echo -e "${GREEN}✓${NC} Installed agent command"

# Add to PATH if needed
SHELL_RC=""
if [[ "$SHELL" == *"zsh"* ]]; then
    SHELL_RC="$HOME/.zshrc"
elif [[ "$SHELL" == *"bash"* ]]; then
    SHELL_RC="$HOME/.bashrc"
fi

if [[ -n "$SHELL_RC" ]] && ! grep -q '.local/bin' "$SHELL_RC" 2>/dev/null; then
    echo '' >> "$SHELL_RC"
    echo '# Terminal Agent' >> "$SHELL_RC"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
    echo -e "${GREEN}✓${NC} Added to PATH in $SHELL_RC"
    NEED_SOURCE=true
else
    echo -e "${GREEN}✓${NC} PATH already configured"
fi

echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""

# Check if we need to source or if it's already in PATH
if command -v agent &> /dev/null; then
    echo -e "Run ${CYAN}agent${NC} to start."
elif [[ "$NEED_SOURCE" == true ]]; then
    echo -e "Run ${CYAN}source $SHELL_RC${NC} then ${CYAN}agent${NC} to start."
    echo -e "  (or open a new terminal)"
else
    echo -e "Run ${CYAN}$BIN_DIR/agent${NC} to start."
    echo -e "  (or open a new terminal for PATH to update)"
fi

echo ""
echo -e "Options:"
echo -e "  ${CYAN}agent${NC}          Start normally"
echo -e "  ${CYAN}agent --yolo${NC}   Autonomous mode (no prompts)"
echo ""
