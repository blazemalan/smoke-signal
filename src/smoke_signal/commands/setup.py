import click


@click.command("setup")
def setup():
    """Run the first-time setup wizard."""
    from smoke_signal.setup_wizard import run_wizard

    completed = run_wizard()
    if completed:
        click.echo("Setup complete!")
    else:
        click.echo("Setup cancelled.")
