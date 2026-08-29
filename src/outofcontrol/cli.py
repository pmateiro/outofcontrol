from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from outofcontrol.config import Settings
from outofcontrol.factory import create_agent

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


def _cli_confirm(tool: str, payload: dict) -> bool:
    if tool == "delete_file":
        body = f"[bold yellow]Sensitive {tool}[/bold yellow]\n\nPath: [cyan]{payload.get('path')}[/cyan]"
    elif tool == "github_pr_merge":
        body = (
            f"[bold yellow]Sensitive {tool}[/bold yellow]\n\n"
            f"PR: [cyan]#{payload.get('number')}[/cyan] "
            f"repo={payload.get('repo')} method={payload.get('method')}"
        )
    else:
        body = (
            f"[bold yellow]Sensitive {tool}[/bold yellow]\n\n"
            f"Command: [cyan]{payload.get('command')}[/cyan]\n"
            f"cwd: {payload.get('cwd')}"
        )
    console.print(Panel(body, title="Confirmation required"))
    return typer.confirm("Allow this action?", default=False)


@app.command()
def chat(
    message: Optional[str] = typer.Argument(None, help="Single-shot message; omit for REPL"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.yaml"),
) -> None:
    """Chat with the agent (REPL or one-shot)."""
    settings = Settings.load(config)
    try:
        agent, _, _ = create_agent(settings, confirm=_cli_confirm)
    except Exception as e:
        console.print(f"[red]Failed to start agent:[/red] {e}")
        raise typer.Exit(1) from e

    def handle(text: str) -> None:
        with console.status("Thinking…"):
            result = agent.run(text)
        if result.pending_confirmations:
            for p in result.pending_confirmations:
                console.print(
                    f"[yellow]Pending confirmation:[/yellow] {p.get('meta', {}).get('command')} "
                    f"(token={p.get('confirmation_token')})"
                )
        console.print(Panel(result.reply or "(empty reply)", title="Agent"))

    if message:
        handle(message)
        return

    console.print(
        "[bold]OutOfControl[/bold] CLI — type a message, or [cyan]/exit[/cyan] to quit. "
        f"provider=[green]{settings.provider}[/green] model=[green]{settings.model}[/green]"
    )
    while True:
        try:
            text = console.input("[bold blue]you>[/bold blue] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        if not text:
            continue
        if text in {"/exit", "/quit", ":q"}:
            break
        if text == "/reset":
            agent.reset()
            console.print("[dim]History cleared[/dim]")
            continue
        handle(text)


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8000, help="Bind port"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Run the HTTP API (for testing from other devices on the same network, bind 0.0.0.0)."""
    import uvicorn

    from outofcontrol.api import create_app

    settings = Settings.load(config)
    api = create_app(settings)
    console.print(f"API on http://{host}:{port}  (docs at /docs)")
    uvicorn.run(api, host=host, port=port)


@app.command("watch")
def watch(
    once: bool = typer.Option(False, "--once", help="Check once and exit"),
    interval: Optional[float] = typer.Option(
        None, "--interval", "-i", help="Poll interval seconds (default from config)"
    ),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    no_desktop: bool = typer.Option(
        False, "--no-desktop", help="Skip notify-send desktop notifications"
    ),
) -> None:
    """Watch the local calendar and fire due reminders (console + optional desktop/webhook)."""
    from outofcontrol.reminders import build_notifiers, run_loop

    settings = Settings.load(config)
    calendar_path = settings.resolve_calendar_path()
    poll = interval if interval is not None else settings.reminder_poll_seconds
    notifiers = build_notifiers(
        desktop=settings.reminder_desktop and not no_desktop,
        webhook_url=settings.reminder_webhook_url,
    )
    console.print(
        f"Watching [cyan]{calendar_path}[/cyan] "
        f"(interval={poll}s, once={once})"
    )
    try:
        run_loop(
            calendar_path,
            interval_seconds=poll,
            defaults=settings.default_remind_minutes,
            notifiers=notifiers,
            once=once,
        )
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped watching[/dim]")


if __name__ == "__main__":
    app()
