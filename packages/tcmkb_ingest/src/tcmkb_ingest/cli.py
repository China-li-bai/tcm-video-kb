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
    )
    # Compact summary
    summary = {k: ({"skipped": v.get("skipped"), "vk": v.get("version_key"),
                    "metrics": v.get("metrics")} if isinstance(v, dict) else v)
               for k, v in result["steps"].items()}
    click.echo(json.dumps({"video_id": video_id, "to": to_step, "steps": summary},
                          ensure_ascii=False, indent=2))

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
