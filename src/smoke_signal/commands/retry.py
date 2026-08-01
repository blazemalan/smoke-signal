from pathlib import Path

import click

from smoke_signal.config import DEFAULT_DB_PATH
from smoke_signal.watcher.state import get_failed, init_db, requeue_failed


@click.command("retry")
@click.option("--list", "list_only", is_flag=True, help="List failed jobs without changing their status")
def retry(list_only: bool = False) -> None:
    """List and requeue failed watcher jobs."""
    if not DEFAULT_DB_PATH.exists():
        click.echo("Watcher database not found. Start with: smoke-signal watch")
        return

    init_db(DEFAULT_DB_PATH)
    failed_jobs = get_failed(DEFAULT_DB_PATH)

    if not failed_jobs:
        click.echo("No failed jobs found.")
        return

    if list_only:
        click.echo(f"Found {len(failed_jobs)} failed job(s):")
        for job in failed_jobs:
            name = Path(job["file_path"]).name
            error = job.get("error_message") or "Unknown error"
            click.echo(f"  - {name}: {error}")
        return

    count = requeue_failed(DEFAULT_DB_PATH)
    click.echo(f"Re-queued {count} failed job(s).")
    for job in failed_jobs:
        name = Path(job["file_path"]).name
        click.echo(f"  - {name}")
    click.echo("The watcher will pick these up automatically if it is running.")
