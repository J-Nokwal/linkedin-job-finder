"""Centralised rich logging helper for LinkedIn Job Finder."""

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

_THEME = Theme({
    "tag.main":      "bold cyan",
    "tag.scraper":   "bold blue",
    "tag.analyzer":  "bold magenta",
    "tag.worker":    "bold green",
    "lvl.info":      "white",
    "lvl.success":   "bold green",
    "lvl.warning":   "bold yellow",
    "lvl.error":     "bold red",
    "lvl.debug":     "dim white",
    "muted":         "dim white",
    "action.apply":  "bold green",
    "action.save":   "bold yellow",
    "action.skip":   "dim white",
})

_MODULE_STYLES: dict[str, tuple[str, str]] = {
    "MAIN":     ("tag.main",     "cyan"),
    "SCRAPER":  ("tag.scraper",  "blue"),
    "ANALYZER": ("tag.analyzer", "magenta"),
    "WORKER":   ("tag.worker",   "green"),
}

console = Console(theme=_THEME, highlight=False)


class Logger:
    """Per-module logger.  Usage: log = Logger("SCRAPER")"""

    def __init__(self, module: str):
        self.module = module.upper()
        tag_style, self._color = _MODULE_STYLES.get(
            self.module, ("bold white", "white")
        )
        self._tag = f"[{tag_style}][{self.module}][/{tag_style}]"

    def info(self, msg: str) -> None:
        console.print(f"{self._tag} {msg}")

    def success(self, msg: str) -> None:
        console.print(f"{self._tag} [lvl.success]✅  {msg}[/lvl.success]")

    def warning(self, msg: str) -> None:
        console.print(f"{self._tag} [lvl.warning]⚠️   {msg}[/lvl.warning]")

    def error(self, msg: str) -> None:
        console.print(f"{self._tag} [lvl.error]❌  {msg}[/lvl.error]")

    def debug(self, msg: str) -> None:
        console.print(f"{self._tag} [lvl.debug]{msg}[/lvl.debug]")

    def skip(self, msg: str) -> None:
        console.print(f"{self._tag} [muted]⏭   {msg}[/muted]")

    def rule(self, title: str = "") -> None:
        console.rule(
            f"[bold {self._color}]{title}[/bold {self._color}]" if title else "",
            style=self._color,
        )

    def section(self, title: str) -> None:
        console.print(
            Panel(
                f"[bold]{title}[/bold]",
                border_style=self._color,
                expand=False,
                padding=(0, 2),
            )
        )

    def banner(self, title: str, subtitle: str = "") -> None:
        body = f"[bold white]{title}[/bold white]"
        if subtitle:
            body += f"\n[muted]{subtitle}[/muted]"
        console.print(Panel(body, border_style=self._color, padding=(1, 4)))

    def step(self, msg: str) -> None:
        console.print(f"  [muted]→[/muted] {msg}")

    def alert(self, title: str, lines: list[str], style: str = "yellow") -> None:
        body = "\n".join(lines)
        console.print(Panel(body, title=f"[bold]{title}[/bold]", border_style=style, padding=(1, 2)))

    def kv(self, key: str, value: str) -> None:
        console.print(f"  [muted]{key}:[/muted] [bold]{value}[/bold]")


def job_card(index: int, job: dict) -> None:
    """Render a single matched job as a rich table card."""
    role      = job.get("role_detected")    or "Unknown Role"
    company   = job.get("company_detected") or "Unknown Company"
    location  = job.get("location_detected") or "Unknown"
    posted    = job.get("date_posted")      or "—"
    score     = job.get("fit_score", 0)
    relevance = job.get("job_relevance_0_100")
    reason    = job.get("fit_reason")       or ""
    link      = job.get("apply_link")       or "no link found"
    action    = (job.get("action") or "skip").upper()
    post_kind = (job.get("post_kind") or "").strip()
    reqs      = [r for r in (job.get("requirements") or []) if r]

    action_style = {
        "APPLY NOW":      "action.apply",
        "SAVE FOR LATER": "action.save",
    }.get(action, "action.skip")

    t = Table.grid(padding=(0, 1))
    t.add_column(style="muted", justify="right", min_width=12)
    t.add_column()

    meta_parts: list[str] = []
    if post_kind:
        meta_parts.append(post_kind)
    if relevance is not None:
        meta_parts.append(f"relevance {relevance}/100")

    t.add_row("Role",     f"[bold white]{role}[/bold white] @ [bold]{company}[/bold]")
    if meta_parts:
        t.add_row("Kind",     " | ".join(meta_parts))
    t.add_row("Location", f"📍 {location}   Posted: {posted}")
    t.add_row("Fit score", f"[bold green]{score}/100[/bold green]")
    t.add_row("Reason",   reason)
    if reqs:
        shown = reqs[:3]
        extra = len(reqs) - 3
        req_text = "\n".join(f"• {r}" for r in shown)
        if extra > 0:
            req_text += f"\n[muted]… (+{extra} more)[/muted]"
        t.add_row("Requirements", req_text)
    t.add_row("Link",     f"[link={link}]{link}[/link]")
    t.add_row("Action",   f"[{action_style}]⚡ {action}[/{action_style}]")

    console.print(
        Panel(t, title=f"[bold]#{index}[/bold]", border_style="green", padding=(0, 1))
    )


def summary_table(jobs: list[dict]) -> None:
    """Compact summary table of all matched jobs."""
    t = Table(
        title="Matched Jobs",
        border_style="cyan",
        header_style="bold cyan",
        show_lines=True,
    )
    t.add_column("#",        style="muted",       width=4,  justify="right")
    t.add_column("Role",     style="bold white",  min_width=22)
    t.add_column("Company",  style="white",       min_width=16)
    t.add_column("Score",    style="bold green",  width=7,  justify="center")
    t.add_column("Action",   width=16)

    for i, job in enumerate(jobs, 1):
        action = (job.get("action") or "skip").upper()
        action_style = {
            "APPLY NOW":      "bold green",
            "SAVE FOR LATER": "bold yellow",
        }.get(action, "dim")
        t.add_row(
            str(i),
            job.get("role_detected")    or "—",
            job.get("company_detected") or "—",
            str(job.get("fit_score", 0)),
            f"[{action_style}]{action}[/{action_style}]",
        )
    console.print(t)
