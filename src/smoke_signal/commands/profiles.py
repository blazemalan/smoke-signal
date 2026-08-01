from pathlib import Path
import click

from smoke_signal.config import DEFAULT_PROFILES_DIR, get_hf_token


@click.command("enroll")
@click.argument("name")
@click.argument("audio_file", type=click.Path(exists=True, path_type=Path))
@click.option("--append", is_flag=True, help="Add to existing profile instead of replacing")
def enroll(name, audio_file, append):
    """Enroll a speaker from an audio file for future identification.

    Provide 30-60 seconds of solo speech for best results.
    """
    from smoke_signal.enrollment.manager import enroll_speaker
    from smoke_signal.gpu import check_gpu

    gpu_info = check_gpu()
    device = gpu_info["device"]
    hf_token = get_hf_token()

    DEFAULT_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    profile_path = enroll_speaker(
        name=name,
        audio_path=audio_file,
        profiles_dir=DEFAULT_PROFILES_DIR,
        hf_token=hf_token,
        append=append,
        device=device,
    )
    click.echo(f"Profile saved: {profile_path}")


@click.group()
def profiles():
    """Manage speaker profiles."""
    pass


@profiles.command("list")
def profiles_list():
    """List all enrolled speaker profiles."""
    from smoke_signal.enrollment.manager import list_profiles

    profs = list_profiles(DEFAULT_PROFILES_DIR)
    if not profs:
        click.echo("No speaker profiles found.")
        click.echo(f"Enroll a speaker: smoke-signal enroll <name> <audio_file>")
        return

    click.echo(f"{'Name':<15} {'Samples':<10} {'Created':<12} {'Updated':<12}")
    click.echo("-" * 50)
    for p in profs:
        created = p["created"][:10]
        updated = p["updated"][:10]
        click.echo(f"{p['name']:<15} {p['num_samples']:<10} {created:<12} {updated:<12}")


@profiles.command("delete")
@click.argument("name")
def profiles_delete(name):
    """Delete a speaker profile."""
    from smoke_signal.enrollment.manager import delete_profile

    if delete_profile(name, DEFAULT_PROFILES_DIR):
        click.echo(f"Deleted profile '{name}'.")
    else:
        click.echo(f"Profile '{name}' not found.")


@profiles.command("rename")
@click.argument("old_name")
@click.argument("new_name")
def profiles_rename(old_name, new_name):
    """Rename a speaker profile."""
    from smoke_signal.enrollment.manager import rename_profile

    if rename_profile(old_name, new_name, DEFAULT_PROFILES_DIR):
        click.echo(f"Renamed profile '{old_name}' to '{new_name}'.")
    else:
        click.echo(f"Profile '{old_name}' not found or '{new_name}' already exists.")
