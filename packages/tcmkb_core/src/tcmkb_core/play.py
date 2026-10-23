"""Site watch URLs + play-audio key / URL construction (LocalStorage stub or R2 env).

Domestic playback decision (2026-10): 64 kbps AAC/m4a on R2 (or data/r2-mirror),
cite primary link is /watch/{video_id}?t=<sec>; YouTube id/url kept as backup.
"""
from __future__ import annotations
import hashlib, hmac, math, os, pathlib, time
from typing import Any
from urllib.parse import quote

YT_WATCH = "https://www.youtube.com/watch?v="


def site_watch_url(video_id: str | None, t: float | None = None, *,
                   end: float | None = None, base: str = "") -> str | None:
    """In-site deep link: /watch/{video_id}?t=<floor sec>[&end=]. Relative unless base set."""
    if not video_id:
        return None
    path = f"/watch/{video_id}"
    qs: list[str] = []
    if t is not None:
        qs.append(f"t={max(int(math.floor(float(t))), 0)}")
    if end is not None:
        qs.append(f"end={max(int(math.floor(float(end))), 0)}")
    if qs:
        path = f"{path}?{'&'.join(qs)}"
    base = (base or os.environ.get("TCMKB_SITE_BASE") or "").rstrip("/")
    return f"{base}{path}" if base else path


def youtube_t_url(youtube_id: str | None, t: float | None = None) -> str | None:
    """YouTube watch URL, optional &t=<floor sec>s. Backup / source field only."""
    if not youtube_id:
        return None
    u = f"{YT_WATCH}{youtube_id}"
    if t is not None:
        u += f"&t={max(int(math.floor(float(t))), 0)}s"
    return u


def play_audio_key(video_id: str) -> str:
    """R2 / LocalStorage object key for the 64 kbps AAC play copy."""
    return f"play/{video_id}.m4a"


def _r2_configured() -> bool:
    return bool(os.environ.get("R2_ACCOUNT_ID") and os.environ.get("R2_ACCESS_KEY_ID")
                and os.environ.get("R2_SECRET_ACCESS_KEY"))


def _hmac_token(video_id: str, expires: int, secret: str) -> str:
    msg = f"{video_id}:{expires}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()[:32]


def construct_play_url(video_id: str, *, root: str | pathlib.Path | None = None,
                       expires_s: int = 14400, mirror_dir: str | pathlib.Path | None = None
                       ) -> dict[str, Any]:
    """Return play URL metadata for a video's 64 kbps m4a.

    - Local (default): ``/api/media/{video_id}`` (+ absolute path under r2-mirror when present).
    - R2 env set: HMAC-token stub URL (no real AWS signature; production wires boto3 separately).
    Tests can monkeypatch env / pass mirror_dir.
    """
    key = play_audio_key(video_id)
    expires_s = int(expires_s)
    out: dict[str, Any] = {"video_id": video_id, "key": key, "expires_s": expires_s}

    if _r2_configured():
        secret = os.environ.get("R2_SECRET_ACCESS_KEY") or "dev"
        exp = int(time.time()) + expires_s
        token = _hmac_token(video_id, exp, secret)
        domain = (os.environ.get("R2_PUBLIC_BASE")
                  or os.environ.get("TCMKB_MEDIA_BASE")
                  or f"{os.environ.get('R2_BUCKET', 'tcm-media')}.r2.stub")
        domain = domain.rstrip("/")
        if "://" not in domain:
            domain = f"https://{domain}"
        url = f"{domain}/{key}?exp={exp}&token={token}"
        out.update(url=url, mode="r2-presign-stub", bucket=os.environ.get("R2_BUCKET", "tcm-media"))
        return out

    # Local mirror stub
    if mirror_dir is None and root is not None:
        from tcmkb_core.config import load_pipeline_config
        pipe = load_pipeline_config(pathlib.Path(root))
        mirror_dir = pathlib.Path(root) / pipe.get("r2_mirror", "data/r2-mirror")
    path = None
    if mirror_dir is not None:
        p = pathlib.Path(mirror_dir) / key
        if p.is_file():
            path = str(p.resolve())
    out.update(url=f"/api/media/{quote(video_id, safe='')}", mode="local", path=path)
    return out


def verify_media_token(video_id: str, exp: int | str, token: str,
                       secret: str | None = None) -> bool:
    """Validate stub HMAC token from construct_play_url (r2-presign-stub mode)."""
    try:
        exp_i = int(exp)
    except (TypeError, ValueError):
        return False
    if exp_i < int(time.time()):
        return False
    secret = secret or os.environ.get("R2_SECRET_ACCESS_KEY") or "dev"
    return hmac.compare_digest(_hmac_token(video_id, exp_i, secret), token or "")
