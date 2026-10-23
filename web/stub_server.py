#!/usr/bin/env python3
"""Minimal watch + play-url + Range media stub (stdlib only)."""
from __future__ import annotations
import argparse, json, mimetypes, os, pathlib, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "tcmkb_core" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "tcmkb_ingest" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "tcmkb_lexicon" / "src"))

from tcmkb_core.config import load_pipeline_config  # noqa: E402
from tcmkb_core.play import construct_play_url, play_audio_key, verify_media_token  # noqa: E402


def _mirror() -> pathlib.Path:
    pipe = load_pipeline_config(ROOT)
    return ROOT / pipe.get("r2_mirror", "data/r2-mirror")


def _media_path(video_id: str) -> pathlib.Path | None:
    p = _mirror() / play_audio_key(video_id)
    return p if p.is_file() else None


WATCH_HTML = """<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"/>
<title>{vid}</title>
<body style="font-family:system-ui;max-width:40rem;margin:2rem auto">
<h1>{vid}</h1>
<p>t={t}{end_label}</p>
<audio id="a" controls preload="metadata" src="{src}" style="width:100%"></audio>
<p><a href="{play_api}">play-url JSON</a> · YouTube backup is not used for primary playback.</p>
<script>
const a = document.getElementById('a');
const t = {t};
const end = {end_js};
a.addEventListener('loadedmetadata', () => {{ a.currentTime = t; a.play().catch(()=>{{}}); }});
if (end != null) a.addEventListener('timeupdate', () => {{ if (a.currentTime >= end) a.pause(); }});
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quieter
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Accept-Ranges", "bytes")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        path = unquote(u.path)
        qs = parse_qs(u.query)

        if path.startswith("/watch/"):
            vid = path[len("/watch/"):].strip("/")
            if not vid or "/" in vid:
                return self._send(400, b"bad video_id", "text/plain")
            t = int(float(qs.get("t", ["0"])[0] or 0))
            end = qs.get("end", [None])[0]
            end_js = "null" if end is None else str(int(float(end)))
            end_label = "" if end is None else f" end={end}"
            src = f"/api/media/{vid}"
            html = WATCH_HTML.format(vid=vid, t=t, end_js=end_js, end_label=end_label,
                                     src=src, play_api=f"/api/play-url/{vid}")
            return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")

        if path.startswith("/api/play-url/"):
            vid = path[len("/api/play-url/"):].strip("/")
            meta = construct_play_url(vid, root=ROOT, expires_s=int(qs.get("expires", ["14400"])[0]))
            body = json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8")
            return self._send(200, body, "application/json; charset=utf-8")

        if path.startswith("/api/media/"):
            vid = path[len("/api/media/"):].strip("/")
            # Optional token gate when R2 stub query present
            if "token" in qs and "exp" in qs:
                if not verify_media_token(vid, qs["exp"][0], qs["token"][0]):
                    return self._send(403, b"invalid or expired token", "text/plain")
            fp = _media_path(vid)
            if not fp:
                return self._send(404, f"no play audio for {vid} (run s02_media)".encode(), "text/plain")
            data = fp.read_bytes()
            ctype = mimetypes.guess_type(fp.name)[0] or "audio/mp4"
            rng = self.headers.get("Range")
            if rng and rng.startswith("bytes="):
                try:
                    start_s, end_s = rng[6:].split("-", 1)
                    start = int(start_s) if start_s else 0
                    end = int(end_s) if end_s else len(data) - 1
                    end = min(end, len(data) - 1)
                    chunk = data[start:end + 1]
                    self.send_response(206)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
                    self.send_header("Content-Length", str(len(chunk)))
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                    self.wfile.write(chunk)
                    return
                except Exception:
                    pass
            return self._send(200, data, ctype)

        if path in ("/", "/health"):
            return self._send(200, b'{"ok":true,"service":"tcmkb-web-stub"}\n', "application/json")
        self._send(404, b"not found", "text/plain")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    # Load configs/.env names into os.environ if present (no secrets committed)
    envp = ROOT / "configs" / ".env"
    if envp.is_file():
        for ln in envp.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"tcmkb web stub http://{args.host}:{args.port}/watch/<video_id>?t=0  mirror={_mirror()}",
          flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
