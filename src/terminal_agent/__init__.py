"""Terminal Agent - A coding agent for the terminal, powered by Ollama Cloud."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("open-terminal-agent")
except PackageNotFoundError:
    __version__ = "dev"  # Fallback when running from source without install

from terminal_agent.agent import run_agent

__all__ = ["run_agent", "__version__"]
