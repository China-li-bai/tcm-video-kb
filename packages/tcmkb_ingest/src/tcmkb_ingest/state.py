"""SQLite-backed step_run / video tables for local MVP (swap to Postgres later)."""
from __future__ import annotations
import json, sqlite3, pathlib, datetime
from typing import Any, Optional
from tcmkb_core.models import StepRun, VideoManifest

SCHEMA = """
CREATE TABLE IF NOT EXISTS video (
  video_id        TEXT PRIMARY KEY,
  series_id       TEXT NOT NULL,
  episode         INTEGER NOT NULL DEFAULT 0,
  title           TEXT NOT NULL DEFAULT '',
  source_path     TEXT NOT NULL,
  source_sha256   TEXT UNIQUE NOT NULL,
  source_bytes    INTEGER,
  duration_s      REAL,
  r2_source_key   TEXT,
  r2_play_key     TEXT,
  r2_audio_key    TEXT,
  active_versions TEXT NOT NULL DEFAULT '{}',
  ext             TEXT,
  meta            TEXT NOT NULL DEFAULT '{}',
  created_at      TEXT
);
CREATE TABLE IF NOT EXISTS step_run (
  video_id      TEXT NOT NULL,
  step          TEXT NOT NULL,
  version_key   TEXT NOT NULL,
  status        TEXT NOT NULL,
  attempt       INTEGER NOT NULL DEFAULT 0,
  worker_id     TEXT,
  lease_until   TEXT,
  input_hash    TEXT,
  output_uri    TEXT,
  output_hash   TEXT,
  metrics       TEXT,
  error         TEXT,
  started_at    TEXT,
  finished_at   TEXT,
  PRIMARY KEY (video_id, step, version_key)
);
CREATE INDEX IF NOT EXISTS ix_step_run_status ON step_run (status, step);
-- Heavy media (source audio, wav parts, play copies) deleted after verified outputs.
-- active=1: purged items are never re-run / re-required; re-fetch from source_url.
CREATE TABLE IF NOT EXISTS media_purge (
  video_id      TEXT PRIMARY KEY,
  series_id     TEXT,
  episode       INTEGER,
  title         TEXT,
  youtube_id    TEXT,
  source_url    TEXT,
  source_path   TEXT,
  source_sha256 TEXT,
  source_bytes  INTEGER,
  duration_s    REAL,
  bytes_freed   INTEGER,
  files         TEXT,
  verify        TEXT,
  batch_id      TEXT,
  active        INTEGER NOT NULL DEFAULT 1,
  purged_at     TEXT
);
"""

def _now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")

class StateDB:
    def __init__(self, path: str | pathlib.Path):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), timeout=60)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def upsert_video(self, m: VideoManifest) -> None:
        self.conn.execute(
            """INSERT INTO video (video_id,series_id,episode,title,source_path,source_sha256,
               source_bytes,duration_s,r2_source_key,r2_play_key,r2_audio_key,active_versions,ext,meta,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(video_id) DO UPDATE SET
                 title=excluded.title, source_path=excluded.source_path,
                 source_sha256=excluded.source_sha256, source_bytes=excluded.source_bytes,
                 duration_s=excluded.duration_s, r2_source_key=excluded.r2_source_key,
                 r2_play_key=excluded.r2_play_key, r2_audio_key=excluded.r2_audio_key,
                 active_versions=excluded.active_versions, ext=excluded.ext, meta=excluded.meta
            """,
            (m.video_id, m.series_id, m.episode, m.title, m.source_path, m.source_sha256,
             m.source_bytes, m.duration_s, m.r2_source_key, m.r2_play_key, m.r2_audio_key,
             json.dumps(m.active_versions, ensure_ascii=False), m.ext,
             json.dumps(m.meta, ensure_ascii=False), _now()),
        )
        self.conn.commit()

    def get_video(self, video_id: str) -> Optional[VideoManifest]:
        row = self.conn.execute("SELECT * FROM video WHERE video_id=?", (video_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["active_versions"] = json.loads(d.get("active_versions") or "{}")
        d["meta"] = json.loads(d.get("meta") or "{}")
        d.pop("created_at", None)
        return VideoManifest(**d)

    def set_active_version(self, video_id: str, step: str, vk: str) -> None:
        m = self.get_video(video_id)
        if not m:
            return
        m.active_versions[step] = vk
        self.conn.execute("UPDATE video SET active_versions=? WHERE video_id=?",
                          (json.dumps(m.active_versions), video_id))
        self.conn.commit()

    def ensure_step(self, video_id: str, step: str, version_key: str) -> StepRun:
        row = self.conn.execute(
            "SELECT * FROM step_run WHERE video_id=? AND step=? AND version_key=?",
            (video_id, step, version_key),
        ).fetchone()
        if row:
            return self._row_to_step(row)
        self.conn.execute(
            "INSERT INTO step_run (video_id,step,version_key,status) VALUES (?,?,?,?)",
            (video_id, step, version_key, "pending"),
        )
        self.conn.commit()
        return StepRun(video_id=video_id, step=step, version_key=version_key, status="pending")

    def get_step(self, video_id: str, step: str, version_key: str) -> Optional[StepRun]:
        row = self.conn.execute(
            "SELECT * FROM step_run WHERE video_id=? AND step=? AND version_key=?",
            (video_id, step, version_key),
        ).fetchone()
        return self._row_to_step(row) if row else None

    def find_done(self, video_id: str, step: str, version_key: str) -> Optional[StepRun]:
        sr = self.get_step(video_id, step, version_key)
        if sr and sr.status == "done":
            return sr
        return None

    def claim(self, video_id: str, step: str, version_key: str, worker_id: str,
              lease_seconds: int = 3600) -> bool:
        """SKIP LOCKED-like: UPDATE … WHERE status='pending' (or expired lease)."""
        now = datetime.datetime.now().astimezone()
        lease = (now + datetime.timedelta(seconds=lease_seconds)).isoformat(timespec="seconds")
        now_s = now.isoformat(timespec="seconds")
        cur = self.conn.execute(
            """UPDATE step_run SET status='running', worker_id=?, lease_until=?,
               attempt=attempt+1, started_at=?, error=NULL
               WHERE video_id=? AND step=? AND version_key=?
                 AND (status='pending' OR (status='running' AND (lease_until IS NULL OR lease_until < ?))
                      OR status='failed')
            """,
            (worker_id, lease, now_s, video_id, step, version_key, now_s),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def mark_done(self, video_id: str, step: str, version_key: str,
                  output_uri: str, output_hash: str, metrics: dict[str, Any]) -> None:
        self.conn.execute(
            """UPDATE step_run SET status='done', output_uri=?, output_hash=?, metrics=?,
               finished_at=?, lease_until=NULL, error=NULL
               WHERE video_id=? AND step=? AND version_key=?""",
            (output_uri, output_hash, json.dumps(metrics, ensure_ascii=False),
             _now(), video_id, step, version_key),
        )
        self.conn.commit()
        self.set_active_version(video_id, step, version_key)

    def mark_skipped(self, video_id: str, step: str, version_key: str, reason: str = "") -> None:
        self.conn.execute(
            """UPDATE step_run SET status='skipped', metrics=?, finished_at=?, lease_until=NULL
               WHERE video_id=? AND step=? AND version_key=?""",
            (json.dumps({"reason": reason}), _now(), video_id, step, version_key),
        )
        self.conn.commit()
        self.set_active_version(video_id, step, version_key)

    def mark_failed(self, video_id: str, step: str, version_key: str, error: str) -> None:
        self.conn.execute(
            """UPDATE step_run SET status='failed', error=?, finished_at=?, lease_until=NULL
               WHERE video_id=? AND step=? AND version_key=?""",
            (error[:4000], _now(), video_id, step, version_key),
        )
        self.conn.commit()

    def fail_running(self, video_id: str, step: str, error: str) -> int:
        """Mark any running/pending row of (video, step) failed (used when a runner raises)."""
        cur = self.conn.execute(
            """UPDATE step_run SET status='failed', error=?, finished_at=?, lease_until=NULL
               WHERE video_id=? AND step=? AND status IN ('running','pending')""",
            (error[:4000], _now(), video_id, step),
        )
        self.conn.commit()
        return cur.rowcount

    def failed_steps(self, video_id: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT video_id, step, version_key, attempt, error, finished_at FROM step_run WHERE status='failed'"
        args: tuple = ()
        if video_id:
            q += " AND video_id=?"
            args = (video_id,)
        return [dict(r) for r in self.conn.execute(q + " ORDER BY finished_at", args).fetchall()]

    # ------------------------------------------------------------ media purge
    def record_purge(self, rec: dict[str, Any]) -> None:
        cols = ["video_id", "series_id", "episode", "title", "youtube_id", "source_url",
                "source_path", "source_sha256", "source_bytes", "duration_s", "bytes_freed",
                "files", "verify", "batch_id"]
        vals = [json.dumps(rec.get(c), ensure_ascii=False) if c in ("files", "verify")
                else rec.get(c) for c in cols]
        self.conn.execute(
            f"INSERT OR REPLACE INTO media_purge ({','.join(cols)},active,purged_at) "
            f"VALUES ({','.join('?' * len(cols))},1,?)", (*vals, _now()))
        self.conn.commit()
        m = self.get_video(rec["video_id"])
        if m:
            m.meta = {**(m.meta or {}), "media_purged": True, "purged_at": _now()}
            self.upsert_video(m)

    def get_purge(self, video_id: str, active_only: bool = True) -> Optional[dict[str, Any]]:
        q = "SELECT * FROM media_purge WHERE video_id=?" + (" AND active=1" if active_only else "")
        row = self.conn.execute(q, (video_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        for k in ("files", "verify"):
            d[k] = json.loads(d[k]) if d.get(k) else None
        return d

    def is_purged(self, video_id: str) -> bool:
        return self.get_purge(video_id) is not None

    def clear_purge(self, video_id: str) -> None:
        """Media re-fetched: keep the history row, but allow s00..s05 to run again."""
        self.conn.execute("UPDATE media_purge SET active=0 WHERE video_id=?", (video_id,))
        self.conn.commit()
        m = self.get_video(video_id)
        if m:
            m.meta = {**(m.meta or {}), "media_purged": False}
            self.upsert_video(m)

    def purged_ids(self) -> set[str]:
        return {r[0] for r in self.conn.execute("SELECT video_id FROM media_purge WHERE active=1")}

    @staticmethod
    def _row_to_step(row: sqlite3.Row) -> StepRun:
        d = dict(row)
        d["metrics"] = json.loads(d["metrics"]) if d.get("metrics") else {}
        return StepRun(**d)
