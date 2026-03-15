"""
Console UI - Visual progress and dashboard for AI EPG Bridge
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


def format_duration(seconds):
    """Format seconds into human readable duration."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = int(minutes // 60)
    mins = minutes % 60
    return f"{hours}h {mins}m"


def progress_bar(ratio, width=20):
    """Create a text progress bar."""
    filled = int(ratio * width)
    empty = width - filled
    return f"{'█' * filled}{'░' * empty}"


def dashboard(stats):
    """
    Render the final results dashboard.

    stats dict expects:
        total, known, exact, ai, missing, stale, skipped,
        elapsed_seconds, output_file,
        deploy_ok (bool), git_ok (bool)
    """
    total = stats.get("total", 0)
    known = stats.get("known", 0)
    exact = stats.get("exact", 0)
    ai = stats.get("ai", 0)
    missing = stats.get("missing", 0)
    stale = stats.get("stale", 0)
    matched = known + exact + ai
    rate = (matched / total * 100) if total > 0 else 0
    elapsed = format_duration(stats.get("elapsed_seconds", 0))
    output = stats.get("output_file", "")
    deploy_ok = stats.get("deploy_ok", False)
    git_ok = stats.get("git_ok", False)

    inner = BOX_WIDTH - 2
    sep = "─" * (inner - 4)

    def pct(n):
        if total == 0:
            return "  0.0%"
        return f"{n / total * 100:5.1f}%"

    def row(label, value, show_pct=True):
        val_str = f"{value:,}"
        if show_pct:
            pct_str = f"({pct(value)})"
            content = f"  {label:<20s} {val_str:>6s}  {pct_str:>8s}"
        else:
            content = f"  {label:<20s} {val_str:>6s}"
        padding = inner - len(content) - 2
        return f" {CYAN}║{RESET}{content}{' ' * max(padding, 0)}  {CYAN}║{RESET}"

    def visible_len(s):
        """Length of string excluding ANSI escape codes."""
        import re as _re
        return len(_re.sub(r'\033\[[0-9;]*m', '', s))

    def text_row(content):
        vlen = visible_len(content)
        padding = inner - vlen
        return f" {CYAN}║{RESET}{content}{' ' * max(padding, 0)}{CYAN}║{RESET}"

    def empty_row():
        return f" {CYAN}║{' ' * inner}║{RESET}"

    bar = progress_bar(rate / 100)
    deploy_icon = f"{GREEN}✓ Deployed{RESET}" if deploy_ok else f"{RED}✗ Failed{RESET}"
    git_icon = f"{GREEN}✓ Pushed{RESET}" if git_ok else f"{RED}✗ Failed{RESET}"

    print()
    print(f" {CYAN}╔{'═' * inner}╗{RESET}")
    print(f" {CYAN}║{BOLD}{'RESULTS DASHBOARD':^{inner}}{RESET}{CYAN}║{RESET}")
    print(f" {CYAN}╠{'═' * inner}╣{RESET}")
    print(empty_row())
    print(row("Channels Processed:", total, show_pct=False))
    print(text_row(f"  {sep}"))
    print(row("Known from DB:", known))
    print(row("Exact match:", exact))
    print(row("AI matched:", ai))
    print(row("Missing:", missing))
    if stale > 0:
        print(row("Stale (removed):", stale, show_pct=False))
    print(empty_row())
    print(text_row(f"  Success Rate:  {bar}  {BOLD}{rate:.1f}%{RESET}"))
    print(empty_row())
    print(text_row(f"  Time Elapsed:  {BOLD}{elapsed}{RESET}"))
    print(text_row(f"  Output:  {DIM}{output}{RESET}"))
    print(text_row(f"  Deploy:  {deploy_icon}"))
    print(text_row(f"  GitHub:  {git_icon}"))
    print(empty_row())
    print(f" {CYAN}╚{'═' * inner}╝{RESET}")
    print()


# Auto-enable on import
enable_windows_ansi()
