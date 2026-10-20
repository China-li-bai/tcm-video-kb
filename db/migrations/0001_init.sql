-- PostgreSQL schema for tcm-video-kb (ARCHITECTURE.md §6). Unused in local SQLite MVP.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE series (
  series_id    text PRIMARY KEY,
  title        text NOT NULL,
  collection   text,
  book_id      text,
  sort         int  NOT NULL DEFAULT 0
);

CREATE TABLE video (
  video_id        text PRIMARY KEY,
  series_id       text NOT NULL REFERENCES series,
  episode         int  NOT NULL,
  title           text NOT NULL,
  source_path     text NOT NULL,
  source_sha256   char(64) UNIQUE NOT NULL,
  source_bytes    bigint,
  duration_s      numeric(10,3),
  r2_source_key   text,
  r2_play_key     text,
  r2_play_lo_key  text,
  r2_audio_key    text,
  active_versions jsonb NOT NULL DEFAULT '{}',
  created_at      timestamptz DEFAULT now(),
  UNIQUE (series_id, episode)
);

CREATE TABLE step_run (
  video_id      text NOT NULL REFERENCES video,
  step          text NOT NULL,
  version_key   text NOT NULL,
  status        text NOT NULL CHECK (status IN ('pending','running','done','failed','skipped')),
  attempt       int  NOT NULL DEFAULT 0,
  worker_id     text,
  lease_until   timestamptz,
  input_hash    text,
  output_uri    text,
  output_hash   text,
  metrics       jsonb,
  error         text,
  started_at    timestamptz,
  finished_at   timestamptz,
  PRIMARY KEY (video_id, step, version_key)
);
CREATE INDEX ON step_run (status, step);
