from pathlib import Path

import click

from smoke_signal.config import (
    DEFAULT_PROFILES_DIR,
    DEFAULT_TRANSCRIPTS_DIR,
    get_hf_token,
    get_profile,
    load_config,
)


def do_transcribe(audio_file, model, language, speakers, identify, output, compute_type, profile, vault, batch_size, no_align, format_type="markdown"):
    from smoke_signal.gpu import check_gpu, check_vram_sufficient
    from smoke_signal.output.markdown import format_transcript, get_output_path
    from smoke_signal.output.structured import format_csv, format_json
    from smoke_signal.pipeline.local import transcribe as run_transcribe

    # Load config and merge with profile
    config = load_config()
    if profile:
        available = config.get("profiles", {}) or {}
        if profile not in available:
            names = ", ".join(sorted(available)) or "(none defined)"
            click.secho(
                f"Warning: profile '{profile}' not found in config.yaml — using defaults. "
                f"Available profiles: {names}",
                fg="yellow",
            )
        prof = get_profile(config, profile)
    else:
        prof = config.get("defaults", {})

    # CLI args override profile/defaults
    model = model or prof.get("model", "large-v3")
    language = language or prof.get("language", "auto")
    compute_type = compute_type or prof.get("compute_type", "float16")
    speakers = speakers if speakers is not None else prof.get("speakers")
    if identify is None:
        identify = prof.get("identify", False)

    # GPU check
    gpu_info = check_gpu()
    if gpu_info["available"]:
        click.echo(f"GPU: {gpu_info['name']} ({gpu_info['vram_total_mb']}MB VRAM, CUDA {gpu_info['cuda_version']})")
    else:
        click.echo("Warning: No CUDA GPU detected. Running on CPU (will be slow).")

    ok, msg = check_vram_sufficient(model, compute_type, gpu_info)
    if not ok:
        click.echo(f"Warning: {msg}")
        if not click.confirm("Continue anyway?"):
            return

    device = gpu_info["device"]

    # Resolve align: CLI flag overrides, then profile, then default true
    align = not no_align
    if not no_align:
        align = prof.get("align", True)

    # Run transcription
    result, audio_array = run_transcribe(
        audio_path=audio_file,
        model_name=model,
        compute_type=compute_type,
        language=language if language != "auto" else None,
        num_speakers=speakers,
        device=device,
        batch_size=batch_size,
        align=align,
    )

    # Speaker identification
    if identify:
        from smoke_signal.enrollment.matcher import identify_speakers
        hf_token = get_hf_token()
        result = identify_speakers(
            result, audio_file, DEFAULT_PROFILES_DIR, hf_token, device,
            audio_array=audio_array,
        )

    # Format and write output
    if format_type == "json":
        formatted_text = format_json(result)
    elif format_type == "csv":
        formatted_text = format_csv(result)
    else:
        formatted_text = format_transcript(result, vault_mode=vault)

    # Honor configured output_dir (same behavior as the watcher), falling
    # back to the default transcripts directory.
    configured_dir = prof.get("output_dir")
    output_dir = Path(configured_dir).expanduser() if configured_dir else DEFAULT_TRANSCRIPTS_DIR
    if vault:
        vault_dir = prof.get("vault_dir") or config.get("defaults", {}).get("vault_dir")
        if vault_dir:
            vault_path = Path(vault_dir).expanduser()
            if vault_path.exists():
                output_dir = vault_path

    output_dir.mkdir(parents=True, exist_ok=True)

    if output is None:
        output = get_output_path(audio_file, output_dir, vault_mode=vault)
        if format_type == "json":
            output = output.with_suffix(".json")
        elif format_type == "csv":
            output = output.with_suffix(".csv")

    output.write_text(formatted_text, encoding="utf-8")
    click.echo(f"Transcript saved to: {output}")
