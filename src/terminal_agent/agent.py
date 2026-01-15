#!/usr/bin/env python3
"""
Coding Agent using Ollama Cloud + MiniMax-M2.1
A coding agent with 7 tools: read_file, list_files, write_file, edit_file, run_bash, web_search, web_fetch
"""

import argparse
import json
import readline  # Enables arrow keys, history, and line editing in input()
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ollama import chat, ChatResponse, web_search, web_fetch
from pygments import highlight
from pygments.lexers import get_lexer_for_filename, TextLexer
from pygments.formatters import TerminalFormatter
from rich.console import Console
from rich.markdown import Markdown

# Terminal colors
USER_COLOR = "\033[94m"      # Blue
ASSISTANT_COLOR = "\033[93m"  # Yellow
THINKING_COLOR = "\033[90m"   # Gray
TOOL_COLOR = "\033[92m"       # Green
ERROR_COLOR = "\033[91m"      # Red
RESET = "\033[0m"

# =============================================================================
# SECURITY MODEL
# =============================================================================
# PRIMARY SECURITY: Permission prompts before destructive operations.
# The agent asks for user confirmation before writing files or running commands.
# This is the same model used by Claude Code and similar tools.
#
# SECONDARY: Dangerous command blocklist (below) catches obvious accidents like
# "rm -rf /" before they reach the permission prompt. This is NOT a security
# boundary - these patterns are trivially bypassed. It's a seatbelt warning
# light, not an airbag.
#
# =============================================================================

# =============================================================================
# DANGEROUS COMMAND BLOCKLIST
# =============================================================================
# PURPOSE: Catch obvious/accidental dangerous commands before execution.
# These patterns catch typos, LLM hallucinations, and copy-paste errors.
# NOT a security boundary - trivially bypassed via variable expansion, etc.
# =============================================================================
DANGEROUS_PATTERNS = {
    # System destruction
    r"rm\s+(-[a-zA-Z]*)*\s*-rf\s+/": "Recursively deletes the entire filesystem starting from root - would destroy the operating system and all data",
    r"rm\s+(-[a-zA-Z]*)*\s*-rf\s+/\*": "Deletes everything in the root directory - equivalent to wiping the entire system",
    r"rm\s+(-[a-zA-Z]*)*\s*-rf\s+~": "Recursively deletes your entire home folder - all your personal files, configs, and data",
    r"mkfs\.": "Formats a filesystem - would erase all data on the target disk/partition",
    r"dd\s+.*if=/dev/(zero|random|urandom).*of=/dev/[a-z]": "Overwrites an entire disk with zeros/random data - complete data destruction",
    r">\s*/dev/[a-z]d[a-z]": "Redirects output to overwrite a raw disk device - destroys all data",
    r"shred\s+.*(/dev/[a-z]|/boot|/etc|/usr|/var)": "Securely wipes system-critical locations - unrecoverable destruction",

    # Fork bomb
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:": "Fork bomb - spawns infinite processes until the system crashes from resource exhaustion",

    # Permission disasters
    r"chmod\s+(-[a-zA-Z]*\s+)*777\s+/": "Makes the entire filesystem world-readable/writable - catastrophic security vulnerability",
    r"chmod\s+(-[a-zA-Z]*\s+)*000\s+/": "Removes all permissions from the entire filesystem - system becomes unusable",
    r"chmod\s+.*-R\s+.*\s+/\s*$": "Recursively changes permissions on root filesystem - can break the entire system",
    r"chown\s+.*-R\s+.*\s+/\s*$": "Recursively changes ownership of root filesystem - can break the entire system",

    # System control
    r"\bshutdown\b": "Shuts down the computer",
    r"\breboot\b": "Reboots the computer",
    r"\bpoweroff\b": "Powers off the computer",
    r"\bhalt\b": "Halts the system",
    r"\binit\s+[06]\b": "Changes system runlevel to shutdown (0) or reboot (6)",
    r"kill\s+-9\s+-1": "Sends SIGKILL to ALL processes - crashes the entire system immediately",

    # Security-critical files
    r">\s*/etc/passwd": "Overwrites the user database - locks everyone out of the system",
    r">\s*/etc/shadow": "Overwrites the password database - breaks all authentication",
    r"rm\s+.*(/etc/passwd|/etc/shadow|/etc/sudoers)": "Deletes critical authentication files - breaks system security",

    # Network/firewall
    r"iptables\s+-F": "Flushes all firewall rules - removes network security protections",
    r"ufw\s+disable": "Disables the firewall entirely - exposes system to network attacks",
}

# Model configuration (can be changed via --model flag or /model command)
DEFAULT_MODEL = "minimax-m2.1:cloud"
MODEL = DEFAULT_MODEL


# Permission modes
class PermissionMode:
    """Permission levels for tool execution."""
    DEFAULT = "default"        # Prompt for writes and bash
    ACCEPT_EDITS = "accept-edits"  # Auto-approve edits, prompt for bash
    YOLO = "yolo"              # Auto-approve everything


PERMISSION_MODE = PermissionMode.DEFAULT

# Rich console for pretty output
console = Console()


# Token tracking
class TokenTracker:
    """Tracks cumulative token usage across API calls."""

    def __init__(self) -> None:
        """Initialize token counters to zero."""
        self.total_input = 0
        self.total_output = 0

    def add(self, response):
        """Add tokens from a response."""
        self.total_input += getattr(response, 'prompt_eval_count', 0) or 0
        self.total_output += getattr(response, 'eval_count', 0) or 0

    @property
    def total(self):
        return self.total_input + self.total_output

    def display(self):
        """Return formatted token display."""
        return f"{self.total:,} tokens (in: {self.total_input:,}, out: {self.total_output:,})"


tokens = TokenTracker()


class Spinner:
    """Animated spinner for showing progress during API calls."""

    FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, message: str = "Thinking"):
        self.message = message
        self.stop_event = threading.Event()
        self.thread = None
        self.start_time = None

    def _spin(self):
        """Background thread that animates the spinner."""
        i = 0
        while not self.stop_event.is_set():
            elapsed = int(time.time() - self.start_time)
            frame = self.FRAMES[i % len(self.FRAMES)]
            # \r returns to start of line, we overwrite the line
            sys.stdout.write(f"\r{THINKING_COLOR}{frame} {self.message}... ({elapsed}s){RESET}  ")
            sys.stdout.flush()
            i += 1
            time.sleep(0.1)

    def start(self):
        """Start the spinner."""
        self.start_time = time.time()
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the spinner and clear the line."""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=0.5)
        # Clear the spinner line
        sys.stdout.write("\r" + " " * 50 + "\r")
        sys.stdout.flush()


def syntax_highlight(code: str, filename: str) -> str:
    """Apply syntax highlighting to code based on filename."""
    try:
        lexer = get_lexer_for_filename(filename)
    except Exception:
        lexer = TextLexer()

    formatter = TerminalFormatter()
    return highlight(code, lexer, formatter).rstrip()


# Diff colors (background)
RED_BG = "\033[41m"      # Red background for removed
GREEN_BG = "\033[42m"    # Green background for added
BLACK_TEXT = "\033[30m"  # Black text for contrast


def format_diff(old_text: str, new_text: str) -> str:
    """Format a simple diff showing old (red) vs new (green)."""
    lines = []

    # Show removed lines (red background)
    for line in old_text.split('\n'):
        lines.append(f"{RED_BG}{BLACK_TEXT}- {line}{RESET}")

    # Show added lines (green background)
    for line in new_text.split('\n'):
        lines.append(f"{GREEN_BG}{BLACK_TEXT}+ {line}{RESET}")

    return '\n'.join(lines)


def resolve_path(path_str: str) -> Path:
    """Convert a path string to an absolute Path object."""
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def to_relative_path(path_str: str) -> str:
    """Convert an absolute path to a relative path for cleaner display.

    If the path is within the current working directory, returns a relative path.
    Otherwise returns the original path.
    """
    try:
        path = Path(path_str)
        cwd = Path.cwd()
        # Check if path is within cwd
        rel = path.relative_to(cwd)
        # Return with ./ prefix for clarity
        return f"./{rel}"
    except ValueError:
        # Path is not relative to cwd, return as-is
        return path_str


# ============== TOOLS ==============

def read_file(filename: str) -> dict[str, Any]:
    """Read the full contents of a file.

    Args:
        filename: The path to the file to read (relative or absolute)

    Returns:
        A dictionary with the file path and its contents
    """
    try:
        full_path = resolve_path(filename)
        content = full_path.read_text(encoding="utf-8")
        return {
            "success": True,
            "file_path": str(full_path),
            "content": content
        }
    except FileNotFoundError:
        return {"success": False, "error": f"File not found: {filename}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_files(path: str = ".") -> dict[str, Any]:
    """List files and directories in a given path.

    Args:
        path: The directory path to list (defaults to current directory)

    Returns:
        A dictionary with the path and list of files/directories
    """
    try:
        full_path = resolve_path(path)
        if not full_path.is_dir():
            return {"success": False, "error": f"Not a directory: {path}"}

        items = []
        for item in sorted(full_path.iterdir()):
            items.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file"
            })

        return {
            "success": True,
            "path": str(full_path),
            "items": items
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def write_file(path: str, content: str) -> dict[str, Any]:
    """Create or overwrite a file with the given content.

    Args:
        path: The path to the file to create
        content: The full content to write to the file

    Returns:
        A dictionary indicating success and the file path
    """
    try:
        full_path = resolve_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "path": str(full_path),
            "action": "created"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def edit_file(path: str, old_text: str, new_text: str) -> dict[str, Any]:
    """Edit an existing file by replacing text.

    Replaces the first occurrence of old_text with new_text.

    Args:
        path: The path to the file to edit
        old_text: The exact text to find in the file
        new_text: The text to replace it with

    Returns:
        A dictionary indicating the action taken
    """
    try:
        full_path = resolve_path(path)

        if not full_path.exists():
            return {"success": False, "error": f"File not found: {path}"}

        content = full_path.read_text(encoding="utf-8")
        count = content.count(old_text)
        if count == 0:
            return {
                "success": False,
                "error": "old_text not found in file",
                "path": str(full_path)
            }
        elif count > 1:
            return {
                "success": False,
                "error": f"old_text appears {count} times in file - include more surrounding context to make it unique",
                "path": str(full_path)
            }

        new_content = content.replace(old_text, new_text, 1)
        full_path.write_text(new_content, encoding="utf-8")

        return {
            "success": True,
            "path": str(full_path),
            "action": "edited"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_dangerous_command(command: str) -> dict[str, Any]:
    """Check if a command matches any dangerous pattern.

    Returns:
        A dictionary with is_dangerous (bool) and explanation (str)
    """
    for pattern, explanation in DANGEROUS_PATTERNS.items():
        if re.search(pattern, command, re.IGNORECASE):
            return {"is_dangerous": True, "explanation": explanation}
    return {"is_dangerous": False, "explanation": ""}


def run_bash(command: str, timeout: int = 30, output_lines: str = "both") -> dict[str, Any]:
    """Execute a bash command and return the output.

    Args:
        command: The bash command to execute
        timeout: Maximum seconds to wait (default 30). Use higher values for slow commands:
                 - Quick commands (ls, cat, echo): 5-10 seconds
                 - Medium commands (grep, find): 30 seconds
                 - Build commands (npm install, pip install): 120-300 seconds
                 - Test suites (pytest, npm test): 300-600 seconds
        output_lines: Which part of output to return if truncated (default "both"):
                 - "first": First 50 lines only (good for listing commands)
                 - "last": Last 50 lines only (good for seeing final results/errors)
                 - "both": First 25 + last 25 lines (good for builds, tests)
                 - "all": No truncation, return everything (use for short outputs)

    Returns:
        A dictionary with stdout, stderr, and exit_code
    """
    # Check for dangerous commands FIRST - these are blocked unconditionally
    danger_check = check_dangerous_command(command)
    if danger_check["is_dangerous"]:
        return {
            "success": False,
            "blocked": True,
            "error": f"BLOCKED: This command is dangerous and cannot be executed.",
            "command": command,
            "reason": danger_check["explanation"]
        }

    # Validate/clamp inputs
    timeout = max(1, min(600, timeout))  # 1 second to 10 minutes
    if output_lines not in ("first", "last", "both", "all"):
        output_lines = "both"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=Path.cwd()
        )

        def truncate_output(text: str, max_lines: int = 50) -> str:
            """Truncate output based on output_lines parameter."""
            lines = text.split('\n')
            if len(lines) <= max_lines or output_lines == "all":
                return text

            omitted = len(lines) - max_lines

            if output_lines == "first":
                return '\n'.join(lines[:max_lines]) + f"\n... ({omitted} more lines)"
            elif output_lines == "last":
                return f"... ({omitted} lines omitted)\n" + '\n'.join(lines[-max_lines:])
            else:  # "both"
                half = max_lines // 2
                first_part = '\n'.join(lines[:half])
                last_part = '\n'.join(lines[-half:])
                return first_part + f"\n... ({omitted} lines omitted) ...\n" + last_part

        stdout = truncate_output(result.stdout, max_lines=50)
        stderr = truncate_output(result.stderr, max_lines=20)

        return {
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Command timed out ({timeout}s limit)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Tool registry for dispatching
TOOLS = {
    "read_file": read_file,
    "list_files": list_files,
    "write_file": write_file,
    "edit_file": edit_file,
    "run_bash": run_bash,
    "web_search": web_search,
    "web_fetch": web_fetch,
}

# List of tool functions for Ollama
TOOL_FUNCTIONS = [read_file, list_files, write_file, edit_file, run_bash, web_search, web_fetch]


def prompt_user(action: str, details: str) -> bool:
    """Prompt user for permission before a destructive operation.

    Args:
        action: Short description of the action (e.g., "Write file")
        details: Details about the action (e.g., file path, command)

    Returns:
        True if user approves, False otherwise
    """
    print(f"\n{TOOL_COLOR}{action}{RESET}")
    print(f"  {details}")

    try:
        response = input(f"{USER_COLOR}Allow? [y/N]: {RESET}").strip().lower()
        return response in ('y', 'yes')
    except (KeyboardInterrupt, EOFError):
        print()  # Newline after Ctrl+C
        return False


def check_permission(tool_name: str, args: dict) -> tuple[bool, str | None]:
    """Check if a tool execution is permitted based on current permission mode.

    Args:
        tool_name: Name of the tool to execute
        args: Arguments for the tool

    Returns:
        Tuple of (is_permitted, error_message). error_message is None if permitted.
    """
    # Read operations always allowed
    if tool_name in ("read_file", "list_files", "web_search", "web_fetch"):
        return True, None

    # YOLO mode: everything allowed
    if PERMISSION_MODE == PermissionMode.YOLO:
        return True, None

    # Write/edit operations
    if tool_name == "write_file":
        if PERMISSION_MODE == PermissionMode.ACCEPT_EDITS:
            return True, None
        path = to_relative_path(args.get("path", "?"))
        content = args.get("content", "")
        lines = content.count('\n') + 1 if content else 0
        if not prompt_user("Write file", f"{path} ({lines} lines)"):
            return False, "User declined to write file"
        return True, None

    if tool_name == "edit_file":
        if PERMISSION_MODE == PermissionMode.ACCEPT_EDITS:
            return True, None
        path = to_relative_path(args.get("path", "?"))
        old_text = args.get("old_text", "")
        new_text = args.get("new_text", "")
        # Show a brief diff preview
        old_preview = old_text[:50] + "..." if len(old_text) > 50 else old_text
        new_preview = new_text[:50] + "..." if len(new_text) > 50 else new_text
        details = f"{path}\n  - {repr(old_preview)}\n  + {repr(new_preview)}"
        if not prompt_user("Edit file", details):
            return False, "User declined to edit file"
        return True, None

    # Bash commands - always prompt unless YOLO
    if tool_name == "run_bash":
        command = args.get("command", "?")
        if not prompt_user("Run command", command):
            return False, "User declined to run command"
        return True, None

    return True, None


def execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool by name and return JSON result."""
    if name not in TOOLS:
        return json.dumps({"success": False, "error": f"Unknown tool: {name}"})

    # Check permission before executing
    permitted, error = check_permission(name, arguments)
    if not permitted:
        return json.dumps({"success": False, "error": error})

    try:
        # Handle Ollama web tools (they return special response objects)
        if name == "web_search":
            # Validate max_results is within 1-10 range
            if "max_results" in arguments:
                arguments["max_results"] = max(1, min(10, arguments["max_results"]))

            result = web_search(**arguments)

            # Convert WebSearchResponse to dict
            return json.dumps({
                "success": True,
                "results": [
                    {"title": r.title, "url": r.url, "content": r.content}
                    for r in result.results
                ]
            }, indent=2)

        elif name == "web_fetch":
            result = web_fetch(**arguments)

            # Convert WebFetchResponse to dict
            return json.dumps({
                "success": True,
                "title": result.title,
                "content": result.content[:8000],  # Truncate long content
                "links": result.links[:20] if result.links else []
            }, indent=2)

        # Regular tools (read_file, list_files, write_file, edit_file, run_bash)
        result = TOOLS[name](**arguments)
        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


def format_tool_call(name: str, args: dict) -> str:
    """Format a tool call for clean display."""
    if name == "write_file":
        path = to_relative_path(args.get("path", "?"))
        content = args.get("content", "")
        lines = content.count('\n') + 1 if content else 0
        return f"[Write] {path} ({lines} lines)"

    elif name == "edit_file":
        path = to_relative_path(args.get("path", "?"))
        return f"[Edit] {path}"

    elif name == "read_file":
        filename = to_relative_path(args.get("filename", "?"))
        return f"[Read] {filename}"

    elif name == "list_files":
        path = to_relative_path(args.get("path", "."))
        return f"[List] {path}"

    elif name == "run_bash":
        command = args.get("command", "?")
        return f"Bash({command})"

    elif name == "web_search":
        query = args.get("query", "?")
        max_results = args.get("max_results", 5)
        return f"[Search] \"{query}\" (max {max_results})"

    elif name == "web_fetch":
        url = args.get("url", "?")
        # Truncate long URLs
        if len(url) > 60:
            url = url[:57] + "..."
        return f"[Fetch] {url}"

    else:
        return f"[{name}] {args}"


def format_tool_result(name: str, result_json: str, args: dict = None) -> str:
    """Format a tool result for clean display."""
    try:
        result = json.loads(result_json)
    except Exception:
        return result_json

    if not result.get("success", False):
        return f"Error: {result.get('error', 'Unknown error')}"

    if name == "write_file":
        path = to_relative_path(result.get('path', '?'))
        output = f"Created {path}"
        # Show first 8 lines as preview with syntax highlighting
        if args and "content" in args:
            lines = args["content"].split('\n')[:8]
            preview_code = '\n'.join(lines)
            if len(args["content"].split('\n')) > 8:
                preview_code += "\n..."
            # Apply syntax highlighting
            highlighted = syntax_highlight(preview_code, path)
            # Indent each line
            preview = '\n'.join(f"    {line}" for line in highlighted.split('\n'))
            output += f"\n{preview}"
        return output

    elif name == "edit_file":
        path = to_relative_path(result.get('path', '?'))
        output = f"Edited {path}"
        # Show diff if we have old_text and new_text
        if args and "old_text" in args and "new_text" in args:
            diff = format_diff(args["old_text"], args["new_text"])
            # Indent each line
            diff_indented = '\n'.join(f"    {line}" for line in diff.split('\n'))
            output += f"\n{diff_indented}"
        return output

    elif name == "read_file":
        content = result.get("content", "")
        lines = content.count('\n') + 1 if content else 0
        path = to_relative_path(result.get('file_path', '?'))
        return f"Read {lines} lines from {path}"

    elif name == "list_files":
        items = result.get("items", [])
        path = to_relative_path(result.get('path', '?'))
        return f"Found {len(items)} items in {path}"

    elif name == "run_bash":
        # Check if command was blocked
        if result.get("blocked"):
            reason = result.get("reason", "Unknown reason")
            return f"{ERROR_COLOR}BLOCKED - DANGEROUS COMMAND{RESET}\n  └ {reason}"

        exit_code = result.get("exit_code", -1)
        stdout = result.get("stdout", "").strip()
        stderr = result.get("stderr", "").strip()

        # Format output with └ prefix like Claude Code
        lines = []
        if stdout:
            for line in stdout.split('\n'):
                lines.append(f"  └ {line}")
        if stderr:
            for line in stderr.split('\n'):
                lines.append(f"  └ {ERROR_COLOR}{line}{RESET}")

        if not lines:
            lines.append(f"  └ (no output)")

        output = '\n'.join(lines)
        status = "success" if exit_code == 0 else f"exit {exit_code}"
        return f"({status})\n{output}"

    elif name == "web_search":
        results = result.get("results", [])
        lines = [f"Found {len(results)} results:"]
        for i, r in enumerate(results[:10], 1):  # Show up to 10
            title = r.get("title", "?")[:60]
            url = r.get("url", "?")
            lines.append(f"  {i}. {title}")
            lines.append(f"     {THINKING_COLOR}{url}{RESET}")
        return '\n'.join(lines)

    elif name == "web_fetch":
        title = result.get("title", "?")
        content = result.get("content", "")
        content_len = len(content)
        # Show preview of content
        preview = content[:200].replace('\n', ' ')
        if len(content) > 200:
            preview += "..."
        lines = [
            f"Fetched: {title}",
            f"  Content: {content_len:,} chars",
            f"  Preview: {preview}"
        ]
        return '\n'.join(lines)

    else:
        return result_json


def print_thinking(thinking: str | None):
    """Print the model's thinking/reasoning if present."""
    if thinking:
        print(f"\n{THINKING_COLOR}[Thinking]{RESET}")
        # Truncate very long thinking for readability
        if len(thinking) > 2000:
            print(f"{THINKING_COLOR}{thinking[:2000]}...{RESET}")
        else:
            print(f"{THINKING_COLOR}{thinking}{RESET}")


VERSION = "0.2.0"


def get_short_path() -> str:
    """Get current working directory with ~ for home."""
    cwd = str(Path.cwd())
    home = str(Path.home())
    if cwd.startswith(home):
        return "~" + cwd[len(home):]
    return cwd


def print_banner() -> None:
    """Print the startup banner with ASCII art."""
    short_path = get_short_path()

    # Colors for banner
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    DIM = "\033[2m"

    print(f"""
{CYAN}  ╭─────╮{RESET}
{CYAN}  │{RESET} ◠ ◠ {CYAN}│{RESET}   {GREEN}Terminal Coder{RESET} {DIM}v{VERSION}{RESET}
{CYAN}  │{RESET}  ▽  {CYAN}│{RESET}   {MODEL}
{CYAN}  ╰─────╯{RESET}   {DIM}{short_path}{RESET}
            {DIM}Type /help for commands{RESET}
""")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Terminal Coder - A coding agent powered by Ollama Cloud'
    )
    parser.add_argument(
        '--model', '-m',
        default=DEFAULT_MODEL,
        help=f'Model to use (default: {DEFAULT_MODEL})'
    )
    parser.add_argument(
        '--accept-edits',
        action='store_true',
        help='Auto-approve file writes/edits, still prompt for bash commands'
    )
    parser.add_argument(
        '--yolo',
        action='store_true',
        help='Bypass all permission prompts (dangerous - full autonomous mode)'
    )
    return parser.parse_args()


def run_agent() -> None:
    """Main agent loop."""
    global MODEL, PERMISSION_MODE

    # Parse command line arguments
    args = parse_args()
    MODEL = args.model

    # Set permission mode (yolo takes precedence over accept-edits)
    if args.yolo:
        PERMISSION_MODE = PermissionMode.YOLO
    elif args.accept_edits:
        PERMISSION_MODE = PermissionMode.ACCEPT_EDITS
    else:
        PERMISSION_MODE = PermissionMode.DEFAULT

    print_banner()

    # Warn about permission mode
    if PERMISSION_MODE == PermissionMode.YOLO:
        print(f"{ERROR_COLOR}  !! YOLO MODE - All permissions bypassed !!{RESET}")
        print(f"{ERROR_COLOR}  !! The agent will act without asking !!{RESET}")
        print()
    elif PERMISSION_MODE == PermissionMode.ACCEPT_EDITS:
        print(f"{TOOL_COLOR}  Accept-edits mode: file writes auto-approved{RESET}")
        print()

    messages = []

    # System message to set context (with current date and working directory)
    current_date = datetime.now().strftime("%A, %B %d, %Y")
    current_dir = str(Path.cwd())
    project_name = Path.cwd().name

    system_msg = f"""Today's date is {current_date}.
You are working in: {current_dir}
Project/folder name: {project_name}

You are a helpful coding assistant with access to these tools:
- read_file: Read file contents
- list_files: List directory contents
- write_file: Create new files
- edit_file: Edit existing files
- run_bash: Execute shell commands (with timeout and output_lines parameters)
- web_search: Search the web for information (query, max_results)
- web_fetch: Fetch content from a URL

Use tools when needed. Use web_search to find current information, documentation, or solutions.
Be concise in your responses.

SECURITY GUIDELINES - You must follow these strictly:

1. DANGEROUS COMMANDS: Never generate or execute destructive system commands like:
   - rm -rf / or rm -rf ~ (filesystem destruction)
   - mkfs, dd to disk devices (disk wiping)
   - chmod/chown -R on root (permission destruction)
   - fork bombs, shutdown, reboot, halt
   - Deleting /etc/passwd, /etc/shadow, /etc/sudoers
   If a user asks you to run such commands, REFUSE and explain why it's dangerous.

2. MALICIOUS CODE: When reading or writing code, be vigilant for:
   - Obfuscated code that hides malicious intent
   - Code that exfiltrates data (sending files/env vars to external servers)
   - Backdoors, reverse shells, or unauthorized network listeners
   - Cryptocurrency miners or ransomware patterns
   - Code that modifies system files or escalates privileges
   If you detect malicious code, WARN the user and refuse to execute or propagate it.

3. CODE YOU WRITE: Ensure all code you generate is:
   - Free of security vulnerabilities (SQL injection, XSS, command injection, etc.)
   - Not capable of being weaponized
   - Clear and readable (no unnecessary obfuscation)

4. USER REQUESTS: If a user asks you to create malware, exploits, or destructive tools, REFUSE.
   You may explain security concepts for educational purposes but never produce working attack code.

OUTPUT FORMATTING:
- When outputting markdown (tables, code blocks, lists), just write the markdown directly.
- Do NOT show both "raw" and "rendered" versions of anything.
- Do NOT wrap markdown in code blocks to show "how it looks" - just output the markdown itself.
- The terminal will render your markdown beautifully, so just write it naturally."""

    while True:
        try:
            user_input = input(f"{USER_COLOR}You:{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{ASSISTANT_COLOR}Goodbye!{RESET}")
            break

        if not user_input:
            continue

        # Handle slash commands
        if user_input.startswith("/"):
            cmd = user_input.lower().split()[0]

            if cmd == "/help":
                mode_display = {
                    PermissionMode.DEFAULT: "default (prompts for writes & bash)",
                    PermissionMode.ACCEPT_EDITS: "accept-edits (auto-approve edits)",
                    PermissionMode.YOLO: "yolo (no prompts)",
                }
                print(f"""
{ASSISTANT_COLOR}Available commands:{RESET}
  /help            Show this help message
  /mode            Cycle permission mode (default → accept-edits → yolo)
  /model <name>    Switch to a different model
  /clear           Clear conversation history
  /tokens          Show token usage
  /quit            Exit the agent

{ASSISTANT_COLOR}Current model:{RESET} {MODEL}
{ASSISTANT_COLOR}Permission mode:{RESET} {mode_display[PERMISSION_MODE]}

{ASSISTANT_COLOR}Available tools:{RESET}
  read_file, list_files, write_file, edit_file, run_bash
  web_search, web_fetch
""")
                continue

            elif cmd == "/mode":
                # Cycle through permission modes
                if PERMISSION_MODE == PermissionMode.DEFAULT:
                    PERMISSION_MODE = PermissionMode.ACCEPT_EDITS
                    print(f"{TOOL_COLOR}Permission mode: accept-edits (auto-approve file edits){RESET}\n")
                elif PERMISSION_MODE == PermissionMode.ACCEPT_EDITS:
                    PERMISSION_MODE = PermissionMode.YOLO
                    print(f"{ERROR_COLOR}Permission mode: yolo (all permissions bypassed!){RESET}\n")
                else:
                    PERMISSION_MODE = PermissionMode.DEFAULT
                    print(f"{ASSISTANT_COLOR}Permission mode: default (prompts for writes & bash){RESET}\n")
                continue

            elif cmd == "/model":
                parts = user_input.split(maxsplit=1)
                if len(parts) < 2:
                    print(f"{ASSISTANT_COLOR}Current model: {MODEL}{RESET}")
                    print(f"Usage: /model <model-name>")
                    print(f"Examples: /model llama3:8b (local)")
                    print(f"          /model deepseek-v3.1:671b-cloud")
                    print(f"          /model minimax-m2.1:cloud\n")
                else:
                    MODEL = parts[1].strip()
                    print(f"{ASSISTANT_COLOR}Switched to model: {MODEL}{RESET}\n")
                continue

            elif cmd == "/clear":
                messages.clear()
                tokens.total_input = 0
                tokens.total_output = 0
                print(f"{ASSISTANT_COLOR}Conversation cleared.{RESET}\n")
                continue

            elif cmd == "/tokens":
                print(f"{ASSISTANT_COLOR}{tokens.display()}{RESET}\n")
                continue

            elif cmd in ("/quit", "/exit"):
                print(f"{ASSISTANT_COLOR}Goodbye!{RESET}")
                break

            else:
                print(f"{ERROR_COLOR}Unknown command: {cmd}{RESET}")
                print(f"Type /help for available commands.\n")
                continue

        if user_input.lower() in ("quit", "exit"):
            print(f"{ASSISTANT_COLOR}Goodbye!{RESET}")
            break

        # Add user message
        messages.append({"role": "user", "content": user_input})

        # Agent loop - keep calling until no more tool calls
        while True:
            # Start spinner while waiting for API
            spinner = Spinner("Thinking")
            spinner.start()

            try:
                response: ChatResponse = chat(
                    model=MODEL,
                    messages=[{"role": "system", "content": system_msg}] + messages,
                    tools=TOOL_FUNCTIONS,
                    think=True
                )
            except Exception as e:
                spinner.stop()
                print(f"{ERROR_COLOR}Error calling model: {e}{RESET}")
                messages.pop()  # Remove failed user message
                break
            finally:
                spinner.stop()

            # Track token usage
            tokens.add(response)

            # Add assistant response to history
            messages.append(response.message)

            # Show thinking if present
            print_thinking(response.message.thinking)

            # Check for tool calls
            if response.message.tool_calls:
                for call in response.message.tool_calls:
                    tool_name = call.function.name
                    tool_args = call.function.arguments

                    # Display clean tool call
                    print(f"\n{TOOL_COLOR}{format_tool_call(tool_name, tool_args)}{RESET}")

                    # Execute the tool
                    result = execute_tool(tool_name, tool_args)

                    # Display clean result
                    print(f"{TOOL_COLOR}  -> {format_tool_result(tool_name, result, tool_args)}{RESET}")

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_name": tool_name,
                        "content": result
                    })
            else:
                # No tool calls - print response and break inner loop
                if response.message.content:
                    print(f"\n{ASSISTANT_COLOR}Assistant:{RESET}")
                    # Use Rich's built-in markdown rendering (uses markdown-it-py)
                    console.print(Markdown(response.message.content))
                break

        # Show token usage
        print(f"\n{THINKING_COLOR}[{tokens.display()}]{RESET}")
        print()  # Blank line between interactions


if __name__ == "__main__":
    run_agent()
