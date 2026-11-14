"""Site watch URLs + play-audio key / URL construction (LocalStorage stub or R2 env).

Domestic playback decision (2026-10): 64 kbps AAC/m4a on R2 (or data/r2-mirror),
cite primary link is /watch/{video_id}?t=<sec>; YouTube id/url kept as backup.
"""
from __future__ import annotations
import hashlib, hmac, math, os, pathlib, re, time
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

YT_WATCH = "https://www.youtube.com/watch?v="


def valid_source_id(value: object) -> bool:
    """A source-defined slug, never a URL/path/query. Catalog membership is a UI concern."""
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) is not None


def finite_seconds(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def site_watch_url(video_id: str | None, t: float | None = None, *,
                   end: float | None = None, base: str = "") -> str | None:
    """Canonical request location, NOT playback telemetry. Zero omits ``t``.

    Missing time opens the lecture; malformed/nonfinite time fails closed. Finite
    negative seconds clamp to zero. See the shared Python/TS contract fixture.
    ``base``/TCMKB_SITE_BASE is trusted deployment configuration, not citation data.
    """
    if not valid_source_id(video_id):
        return None
    if any(value is not None and not finite_seconds(value) for value in (t, end)):
        return None
    path = f"/watch/{video_id}"
    qs: list[str] = []
    if t is not None and t >= 1:
        qs.append(f"t={math.floor(t)}")
    if end is not None:
        qs.append(f"end={max(math.floor(end), 0)}")
    if qs:
        path = f"{path}?{'&'.join(qs)}"
    base = (base or os.environ.get("TCMKB_SITE_BASE") or "").rstrip("/")
    return f"{base}{path}" if base else path


def youtube_t_url(youtube_id: str | None, t: float | None = None) -> str | None:
    """Allowlisted source backup, never a passed-through arbitrary URL."""
    if not valid_source_id(youtube_id) or (t is not None and not finite_seconds(t)):
        return None
    u = f"{YT_WATCH}{youtube_id}"
    if t is not None:
        u += f"&t={max(math.floor(t), 0)}s"
    return u


def youtube_id_from_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        url = urlsplit(value)
        if url.scheme != "https" or url.username or url.password or url.port not in (None, 443):
            return None
        if url.hostname == "youtu.be":
            yid = url.path.removeprefix("/")
        elif url.hostname in {"youtube.com", "www.youtube.com", "m.youtube.com"} and url.path == "/watch":
            values = parse_qs(url.query).get("v", [])
            yid = values[0] if len(values) == 1 else None
        else:
            return None
        return yid if valid_source_id(yid) else None
    except ValueError:
        return None


def citation_links(video_id: str | None, start_s: float | None, citation: dict) -> dict:
    """Read-only derived links. Ignore stored t_url; retain original url on the caller's copy."""
    yid = citation.get("youtube_id")
    if not valid_source_id(yid):
        yid = (youtube_id_from_url(citation.get("url"))
               or youtube_id_from_url(citation.get("youtube_t_url")))
    return {"t_url": site_watch_url(video_id, start_s), "youtube_id": yid,
            "youtube_t_url": youtube_t_url(yid, start_s)}


def play_audio_key(video_id: str) -> str:
    """R2 / LocalStorage object key for the 64 kbps AAC play copy."""
    return f"play/{video_id}.m4a"


def _r2_configured() -> bool:
    return bool(os.environ.get("R2_ACCOUNT_ID") and os.environ.get("R2_ACCESS_KEY_ID")
                and os.environ.get("R2_SECRET_ACCESS_KEY"))


def _hmac_token(video_id: str, expires: int, secret: str) -> str:
    msg = f"{video_id}:{expires}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()[:32]


_warned_hmac_fallback = False


def _media_hmac_secret() -> str:
    """HMAC secret for stub play tokens — not the R2 object-store key.

    Prefer ``TCMKB_MEDIA_HMAC_SECRET``. Falls back to ``R2_SECRET_ACCESS_KEY`` with a
    one-time warning (legacy), then ``dev`` for local tests.
    """
    global _warned_hmac_fallback
    import logging
    dedicated = os.environ.get("TCMKB_MEDIA_HMAC_SECRET")
    if dedicated:
        return dedicated
    legacy = os.environ.get("R2_SECRET_ACCESS_KEY")
    if legacy:
        if not _warned_hmac_fallback:
            logging.getLogger("tcmkb.play").warning(
                "TCMKB_MEDIA_HMAC_SECRET unset; falling back to R2_SECRET_ACCESS_KEY for "
                "stub HMAC (set TCMKB_MEDIA_HMAC_SECRET to decouple media signing from R2 credentials)"
            )
            _warned_hmac_fallback = True
        return legacy
    return "dev"


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
        secret = _media_hmac_secret()
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
    secret = secret or _media_hmac_secret()
    return hmac.compare_digest(_hmac_token(video_id, exp_i, secret), token or "")
