"""tcmkb / python -m tcmkb_ingest CLI."""
from __future__ import annotations
import json, pathlib, sys
import click
from tcmkb_core.config import repo_root
from tcmkb_core.logging_util import get_logger
from tcmkb_ingest.scheduler import run_pipeline
from tcmkb_ingest.steps.base import Ctx
from tcmkb_ingest.steps import STEP_ORDER, normalize_step

log = get_logger("tcmkb.cli")

@click.group()
@click.option("--root", type=click.Path(file_okay=False), default=None, help="Repo root override")
@click.pass_context
def main(ctx: click.Context, root: str | None):
    """tcm-video-kb ingest CLI."""
    ctx.ensure_object(dict)
    ctx.obj["root"] = pathlib.Path(root).resolve() if root else repo_root()

@main.command("register")
@click.option("--video", "video_id", required=True, help="video_id e.g. zj-demo")
@click.option("--file", "source_file", required=True, type=click.Path(exists=True), help="Local media/wav path")
@click.option("--series", "series_id", default=None, help="series_id (default: prefix of video_id)")
@click.option("--episode", default=0, type=int)
@click.option("--title", default="")
@click.pass_context
def register_cmd(ctx: click.Context, video_id: str, source_file: str, series_id: str | None,
                 episode: int, title: str):
    """Register a local media file as a video (runs s00)."""
    series_id = series_id or video_id.split("-")[0]
    c = Ctx.build(video_id, root=ctx.obj["root"])
    from tcmkb_ingest.steps.s00_register import run as s00
    out = s00(c, source_path=source_file, series_id=series_id, episode=episode, title=title or video_id)
    click.echo(json.dumps(out, ensure_ascii=False, indent=2))

@main.command("run")
@click.option("--video", "video_id", required=True)
@click.option("--to", "to_step", default="s08", show_default=True)
@click.option("--from", "from_step", default=None, help="Resume from this step (inclusive)")
@click.option("--force", is_flag=True, help="Re-run even if version_key done")
@click.option("--from-cache", "from_cache", is_flag=True,
              help="s04: ingest asr-bench JSON instead of running FunASR")
@click.option("--cache-dir", default="/workspace/asr-bench/out", show_default=True)
@click.option("--skip-alt/--no-skip-alt", default=True, show_default=True,
              help="Skip SenseVoice alt ASR (s05)")
@click.option("--file", "source_file", default=None, type=click.Path(exists=True),
              help="If video not registered, register this file first")
@click.option("--series", "series_id", default=None)
@click.option("--title", default="")
@click.pass_context
def run_cmd(ctx: click.Context, video_id: str, to_step: str, from_step: str | None,
            force: bool, from_cache: bool, cache_dir: str, skip_alt: bool,
            source_file: str | None, series_id: str | None, title: str):
    """Run pipeline for one video up to --to step (default s08)."""
    to_step = normalize_step(to_step)
    result = run_pipeline(
        video_id,
        to_step=to_step,
        from_step=from_step,
        force=force,
        from_cache=from_cache,
        skip_alt=skip_alt,
        cache_dir=cache_dir,
        source_path=source_file,
        series_id=series_id or video_id.split("-")[0],
        title=title or video_id,
        root=ctx.obj["root"],
    )
    # Compact summary
    summary = {k: ({"skipped": v.get("skipped"), "vk": v.get("version_key"),
                    "metrics": v.get("metrics")} if isinstance(v, dict) else v)
               for k, v in result["steps"].items()}
    click.echo(json.dumps({"video_id": video_id, "to": to_step, "steps": summary},
                          ensure_ascii=False, indent=2))

@main.command("batch")
@click.option("--manifest", type=click.Path(exists=True, dir_okay=False), default=None,
              help="CSV (file,series[,video_id,episode,title]) or YAML list / {videos:[...]}")
@click.option("--dir", "folder", type=click.Path(exists=True, file_okay=False), default=None,
              help="Folder of media files (use with --series)")
@click.option("--series", "series_id", default=None,
              help="series_id for --dir, or default for manifest rows without one")
@click.option("--glob", "pattern", default=None, help="--dir file pattern (default: media extensions)")
@click.option("--id-scheme", type=click.Choice(["auto", "episode", "stem"]), default="auto",
              show_default=True, help="--dir video_id: {series}-{NNN} from filename number, or stem")
@click.option("--to", "to_step", default="s08", show_default=True)
@click.option("--from", "from_step", default=None)
@click.option("--force", is_flag=True, help="Re-run steps even if version_key done")
@click.option("--from-cache", "from_cache", is_flag=True, help="s04 from asr-bench JSON (no FunASR)")
@click.option("--cache-dir", default="/workspace/asr-bench/out", show_default=True)
@click.option("--skip-alt/--no-skip-alt", default=True, show_default=True)
@click.option("--fail-fast", is_flag=True, help="Stop at first failed video")
@click.option("--limit", type=int, default=0, help="Only first N items")
@click.option("--dry-run", is_flag=True, help="Print the resolved items and exit")
@click.option("--run-id", default=None, help="Report name under data/batch/ (default: timestamp)")
@click.pass_context
def batch_cmd(ctx: click.Context, manifest: str | None, folder: str | None, series_id: str | None,
              pattern: str | None, id_scheme: str, to_step: str, from_step: str | None, force: bool,
              from_cache: bool, cache_dir: str, skip_alt: bool, fail_fast: bool, limit: int,
              dry_run: bool, run_id: str | None):
    """Run s00..--to for many videos with ONE shared ASR model; resumable; continues on failure."""
    from tcmkb_ingest.batch import items_from_dir, items_from_manifest, run_batch
    if bool(manifest) == bool(folder):
        raise click.UsageError("give exactly one of --manifest or --dir")
    if folder and not series_id:
        raise click.UsageError("--dir needs --series")
    items = (items_from_manifest(manifest, default_series=series_id) if manifest
             else items_from_dir(folder, series_id, pattern=pattern, id_scheme=id_scheme))
    if limit:
        items = items[:limit]
    if dry_run:
        for it in items:
            click.echo(f"{it.video_id}\t{it.series_id}\t{it.episode}\t{it.file}")
        return
    rep = run_batch(items, to_step=to_step, from_step=from_step, force=force,
                    from_cache=from_cache, skip_alt=skip_alt, cache_dir=cache_dir,
                    root=ctx.obj["root"], fail_fast=fail_fast, run_id=run_id)
    cols = ("video_id", "status", "wall_sec", "audio_sec", "rtf", "n_corrections", "n_chapters",
            "failed_step", "error")
    click.echo("\t".join(cols))
    for r in rep["items"]:
        click.echo("\t".join("" if r.get(c) is None else str(r.get(c)) for c in cols))
    click.echo(json.dumps({k: rep[k] for k in ("run_id", "n_items", "n_ok", "n_failed", "wall_sec",
                                               "audio_sec_ok", "asr_proc_sec_fresh", "model_load_sec",
                                               "peak_rss_mb", "peak_anon_rss_mb", "report_path")},
                          ensure_ascii=False))
    if rep["n_failed"]:
        sys.exit(2)

@main.command("status")
@click.option("--video", "video_id", required=True)
@click.pass_context
def status_cmd(ctx: click.Context, video_id: str):
    """Show active_versions and step_run rows for a video."""
    c = Ctx.build(video_id, root=ctx.obj["root"])
    m = c.state.get_video(video_id)
    if not m:
        click.echo(f"video {video_id} not found", err=True)
        sys.exit(1)
    rows = c.state.conn.execute(
        "SELECT step, version_key, status, output_hash, metrics FROM step_run WHERE video_id=? ORDER BY step",
        (video_id,),
    ).fetchall()
    click.echo(json.dumps({
        "video": m.model_dump(),
        "step_runs": [dict(r) for r in rows],
    }, ensure_ascii=False, indent=2, default=str))

@main.command("steps")
def steps_cmd():
    """List known pipeline steps."""
    for s in STEP_ORDER:
        click.echo(s)

if __name__ == "__main__":
    main()
