#!/bin/bash
# Run Terminal Coder in a sandboxed Podman container
# Usage: ./run-sandboxed.sh [project-directory]

set -e

IMAGE_NAME="terminal-coder"
PROJECT_DIR="${1:-.}"  # Default to current directory if not specified

# Convert to absolute path
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"

# Build the container if it doesn't exist or if source changed
echo "Building container..."
podman build -t "$IMAGE_NAME" -f Containerfile .

echo ""
echo "Starting Terminal Coder (sandboxed)"
echo "Project directory: $PROJECT_DIR"
echo "Press Ctrl+C to exit (kills everything safely)"
echo "----------------------------------------"
echo ""

# Run the container
# --rm: Remove container after exit
# -it: Interactive terminal
# -v: Mount project directory to /workspace/project
# --read-only: Container filesystem is read-only (extra safety)
# --tmpfs /tmp: Writable tmp directory
# --security-opt=no-new-privileges: Prevent privilege escalation
podman run --rm -it \
    -v "$PROJECT_DIR:/workspace/project:Z" \
    --workdir /workspace/project \
    --tmpfs /tmp \
    --security-opt=no-new-privileges \
    "$IMAGE_NAME" "$@"
