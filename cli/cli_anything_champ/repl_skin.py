"""
repl_skin.py — Unified REPL interface for CHAMP Graph CLI.

Provides styled interactive prompt with command history, colored output,
and a consistent UX following the CLI-Anything pattern.
"""
import sys
from typing import Optional

# Attempt to use prompt_toolkit for a rich REPL; fall back to plain input()
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.styles import Style
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
DIM = "\033[2m"

# CHAMP Graph brand color (teal / #4ECDC4)
BRAND = "\033[38;5;80m"

HISTORY_FILE = "~/.cli-anything-champ/history"


def _supports_color() -> bool:
    """Return True if the terminal supports ANSI colors."""
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    """Wrap text in ANSI color code if colors are supported."""
    if _supports_color():
        return f"{code}{text}{RESET}"
    return text


def print_success(msg: str) -> None:
    print(_c(GREEN, f"✓ {msg}"))


def print_error(msg: str) -> None:
    print(_c(RED, f"✗ {msg}"), file=sys.stderr)


def print_warning(msg: str) -> None:
    print(_c(YELLOW, f"⚠ {msg}"))


def print_info(msg: str) -> None:
    print(_c(CYAN, f"ℹ {msg}"))


def print_header(title: str) -> None:
    width = max(len(title) + 4, 50)
    bar = "─" * width
    print(_c(BRAND, f"┌{bar}┐"))
    padding = " " * ((width - len(title)) // 2)
    print(_c(BRAND, f"│{padding}{_c(BOLD, title)}{padding}│"))
    print(_c(BRAND, f"└{bar}┘"))


def print_banner() -> None:
    """Print the CHAMP Graph REPL banner."""
    print()
    print(_c(BRAND + BOLD, "  ██████╗██╗  ██╗ █████╗ ███╗   ███╗██████╗ "))
    print(_c(BRAND + BOLD, " ██╔════╝██║  ██║██╔══██╗████╗ ████║██╔══██╗"))
    print(_c(BRAND + BOLD, " ██║     ███████║███████║██╔████╔██║██████╔╝"))
    print(_c(BRAND + BOLD, " ██║     ██╔══██║██╔══██║██║╚██╔╝██║██╔═══╝ "))
    print(_c(BRAND + BOLD, " ╚██████╗██║  ██║██║  ██║██║ ╚═╝ ██║██║     "))
    print(_c(BRAND + BOLD, "  ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝     "))
    print()
    print(_c(CYAN, "  Centralized High-context Agent Memory Platform"))
    print(_c(DIM, "  Type 'help' for commands, 'exit' to quit"))
    print()


def print_table(headers: list, rows: list, col_widths: Optional[list] = None) -> None:
    """Print a formatted table."""
    if not rows:
        print(_c(DIM, "  (no results)"))
        return

    if col_widths is None:
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))

    header_line = "  " + "  ".join(
        _c(BOLD, str(h).ljust(col_widths[i])) for i, h in enumerate(headers)
    )
    sep_line = "  " + "  ".join("─" * w for w in col_widths)

    print(header_line)
    print(_c(DIM, sep_line))
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            width = col_widths[i] if i < len(col_widths) else 20
            cells.append(str(cell).ljust(width))
        print("  " + "  ".join(cells))


def create_session(history_path: str = HISTORY_FILE) -> Optional[object]:
    """Create a prompt_toolkit session with history, or None if unavailable."""
    if not HAS_PROMPT_TOOLKIT:
        return None
    import os
    expanded = os.path.expanduser(history_path)
    os.makedirs(os.path.dirname(expanded), exist_ok=True)
    style = Style.from_dict({
        "prompt": "#4ecdc4 bold",
    })
    return PromptSession(
        history=FileHistory(expanded),
        auto_suggest=AutoSuggestFromHistory(),
        style=style,
    )


def get_input(session: Optional[object], prompt_text: str) -> str:
    """Get input from user, using prompt_toolkit session if available."""
    if session is not None and HAS_PROMPT_TOOLKIT:
        try:
            return session.prompt(prompt_text)
        except (KeyboardInterrupt, EOFError):
            raise
    return input(prompt_text)
