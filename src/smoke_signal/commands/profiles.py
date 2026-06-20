import click

from smoke_signal.config import DEFAULT_PROFILES_DIR, get_hf_token


def do_enroll(name, audio_file, append):
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


def do_profiles_list():
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


def do_profiles_delete(name):
    from smoke_signal.enrollment.manager import delete_profile

    if delete_profile(name, DEFAULT_PROFILES_DIR):
        click.echo(f"Deleted profile '{name}'.")
    else:
        click.echo(f"Profile '{name}' not found.")


def do_profiles_rename(old_name, new_name):
    from smoke_signal.enrollment.manager import rename_profile

    if rename_profile(old_name, new_name, DEFAULT_PROFILES_DIR):
        click.echo(f"Renamed profile '{old_name}' to '{new_name}'.")
    else:
        click.echo(f"Profile '{old_name}' not found or '{new_name}' already exists.")
