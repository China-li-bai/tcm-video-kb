#!/usr/bin/env python3
"""Derive the release inventory from committed assets, never from local artifacts.

No ingest imports or writes. --check is read-only. Generation validates everything
before atomically replacing the manifest; no timestamps/absolute paths enter it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path('web/src/data/publish-manifest.json')
LAYERS = {
    'transcript': ('web/public/transcripts', 'segments'),
    'knowledge': ('web/public/knowledge', 'points'),
    'entities': ('web/public/entities', 'mentions'),
    'chapters': ('web/src/data/chapters', None),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def text(value):
    return isinstance(value, str) and bool(value.strip())


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_window(row):
    require(isinstance(row, dict), 'row must be an object')
    require(number(row.get('start_s')) and number(row.get('end_s')),
            'start_s/end_s must be finite numbers')
    require(0 <= row['start_s'] <= row['end_s'], 'invalid time window')


def unique(rows, key):
    values = [row[key] for row in rows]
    require(len(values) == len(set(values)), f'duplicate {key}')


def validate_payload(vid, layer, data):
    key = LAYERS[layer][1]
    if key:
        require(isinstance(data, dict) and data.get('video_id') == vid, f'{vid}: wrong video_id')
        rows = data.get(key)
    else:
        rows = data
    require(isinstance(rows, list), f'{vid}: {layer} must contain an array')
    if layer in ('transcript', 'chapters'):
        require(bool(rows), f'{vid}: empty {layer}')
    for row in rows:
        validate_window(row)
        if layer == 'transcript':
            require(type(row.get('seq')) is int and row['seq'] >= 0 and text(row.get('text')), 'invalid segment')
        elif layer == 'knowledge':
            require(row.get('video_id') == vid and text(row.get('kp_id')) and
                    row['kp_id'].startswith(vid + '.') and text(row.get('statement')) and
                    text(row.get('type')) and isinstance(row.get('evidence_quote'), str) and
                    number(row.get('confidence')) and 0 <= row['confidence'] <= 1, 'invalid knowledge point')
        elif layer == 'entities':
            require(all(text(row.get(k)) for k in ('entity_id', 'label', 'type')), 'invalid entity mention')
            require(row.get('seq') is None or (type(row['seq']) is int and row['seq'] >= 0), 'invalid mention seq')
        else:
            require(row.get('video_id') == vid and text(row.get('chapter_id')) and
                    row['chapter_id'].startswith(vid + '.'), 'invalid chapter')
    if layer in ('transcript', 'knowledge', 'chapters'):
        unique(rows, {'transcript': 'seq', 'knowledge': 'kp_id', 'chapters': 'chapter_id'}[layer])
    if layer == 'transcript':
        require(all(a['start_s'] <= b['start_s'] for a, b in zip(rows, rows[1:])), 'segments not time-sorted')
    if layer == 'entities':
        require(len({(r['entity_id'], r['start_s']) for r in rows}) == len(rows), 'duplicate entity mention')
    return rows


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(root):
    catalog = read_json(root/'web/src/data/lectures.json')['lectures']
    require(isinstance(catalog, list) and bool(catalog), 'empty catalog')
    unique(catalog, 'id')
    by_id = {row['id']: row for row in catalog}
    for vid, row in by_id.items():
        require(re.fullmatch(r'[a-z]+-\d{3}', vid) and row['series'] == vid.split('-')[0], 'invalid catalog identity')
    files = {layer: {p.stem: p for p in (root/folder).glob('*.json')}
             for layer, (folder, _) in LAYERS.items()}
    published = set().union(*(set(paths) for paths in files.values()))
    require(published <= by_id.keys(), f'assets outside catalog: {sorted(published - by_id.keys())}')
    # A published listen slice requires companions, not all 145 catalog entries.
    for layer, paths in files.items():
        require(set(paths) == published, f'missing {layer} companions: {sorted(published - paths.keys())}')
    knowledge_ids = {p.name for p in (root/'data/knowledge').glob('*') if p.is_dir() and not p.name.startswith('_')}
    require(knowledge_ids <= by_id.keys(), 'knowledge id outside catalog')
    entries = []
    for vid in sorted(by_id):
        lecture = by_id[vid]
        row = dict(video_id=vid, series=lecture['series'], in_catalog=True,
                   has_knowledge=vid in knowledge_ids, kp_count=0, chapter_count=0,
                   has_public_transcript=vid in published, transcript_sha256=None, segment_count=0,
                   has_public_knowledge=vid in published, has_public_entities=vid in published,
                   has_bundled_chapters=vid in published,
                   playback='youtube' if text(lecture.get('youtubeId')) else 'none', assets={})
        if vid in knowledge_ids:
            base = root/'data/knowledge'/vid
            for name in ('knowledge_points.jsonl', 'chapters.json', 'entities.jsonl', 'build_report.json'):
                require((base/name).is_file(), f'{vid}: missing knowledge file {name}')
            points = read_jsonl(base/'knowledge_points.jsonl')
            chapters = read_json(base/'chapters.json')
            require(all(p.get('video_id') == vid for p in points), f'{vid}: knowledge identity mismatch')
            require(isinstance(chapters, list) and all(c.get('video_id') == vid for c in chapters), f'{vid}: chapter identity mismatch')
            unique(points, 'kp_id'); unique(chapters, 'chapter_id')
            row.update(kp_count=len(points), chapter_count=len(chapters))
        if vid in published:
            validated = {}
            for layer, paths in files.items():
                path = paths[vid]
                validated[layer] = validate_payload(vid, layer, read_json(path))
                row['assets'][layer] = dict(path=path.relative_to(root).as_posix(), sha256=sha(path), bytes=path.stat().st_size, count=len(validated[layer]))
            segments = validated['transcript']; chapters = validated['chapters']
            require(any(c['start_s'] < s['end_s'] and c['end_s'] > s['start_s'] for c in chapters for s in segments), f'{vid}: chapters/transcript have no time overlap')
            row.update(transcript_sha256=row['assets']['transcript']['sha256'], segment_count=len(segments))
        entries.append(row)
    payload = dict(schema='listen-publish/1', lectures=entries)
    payload['content_sha256'] = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return payload


def public_ids(layer, root=ROOT):
    """Exporter defaults are consumers of the generated manifest, not another list."""
    manifest = read_json(root/MANIFEST)
    require(manifest.get('schema') == 'listen-publish/1', 'unsupported manifest')
    rows = manifest['lectures']; unique(rows, 'video_id')
    flag = {'transcript': 'has_public_transcript', 'knowledge': 'has_public_knowledge', 'entities': 'has_public_entities'}[layer]
    return [r['video_id'] for r in rows if r[flag]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        rendered = json.dumps(generate(args.root), ensure_ascii=False, indent=2) + '\n'
        dest = args.root/MANIFEST
        if args.check:
            require(dest.exists() and dest.read_text(encoding='utf-8') == rendered, 'manifest stale or missing; run python3 web/scripts/publish_manifest.py')
        else:
            temp = dest.with_suffix('.tmp')
            temp.write_text(rendered, encoding='utf-8')
            temp.replace(dest)
        print(f'publish manifest {"checked" if args.check else "generated"}')
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f'publish manifest failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
