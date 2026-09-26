"""
Console UI - coloured progress output for the EPG build
"""
import os
import sys

# --- ANSI Colors ---
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

BOX_WIDTH = 50


def enable_windows_ansi():
    """Enable ANSI escape codes and UTF-8 output on Windows 10+ terminals."""
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # Enable ANSI processing
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            # Set console output to UTF-8
            kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass
        # Reconfigure stdout for UTF-8
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def banner(title):
    """Draw a box banner."""
    inner = BOX_WIDTH - 2
    print()
    print(f" {CYAN}╔{'═' * inner}╗{RESET}")
    print(f" {CYAN}║{BOLD}{title:^{inner}}{RESET}{CYAN}║{RESET}")
    print(f" {CYAN}╚{'═' * inner}╝{RESET}")
    print()


def step(num, total, msg):
    """Print a step header."""
    print(f"\n {BOLD}{CYAN}[Step {num}/{total}]{RESET} {BOLD}{msg}{RESET}")


def success(msg):
    """Print a success line."""
    print(f"    {GREEN}✓{RESET} {msg}")


def warn(msg):
    """Print a warning line."""
    print(f"    {YELLOW}⚠{RESET} {msg}")


def error(msg):
    """Print an error line."""
    print(f"    {RED}✗{RESET} {msg}")


def info(msg):
    """Print an info line."""
    print(f"    {CYAN}→{RESET} {msg}")


# Auto-enable on import
enable_windows_ansi()
