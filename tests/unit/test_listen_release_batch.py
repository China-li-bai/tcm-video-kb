"""PR-6 real release regression; no artifacts/media/network needed in CI.

The immutable receipt binds locally audited source projections to public bytes.
It is historical test evidence, never an input to runtime/export selection.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECEIPT = json.loads((ROOT / 'docs/releases/pr6-jgy-013-015.audit.json').read_text())
BATCH = RECEIPT['episodes']
LAYERS = ('web/public/transcripts', 'web/public/knowledge', 'web/public/entities', 'web/src/data/chapters')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(paths):
    rows = [(p.relative_to(ROOT).as_posix(), sha(p)) for p in sorted(paths)]
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def test_original_21_assets_and_all_raw_knowledge_are_byte_identical():
    baseline = RECEIPT['baseline']
    paths = [ROOT / folder / f'{vid}.json' for folder in LAYERS for vid in baseline['video_ids']]
    assert len(paths) == baseline['asset_count'] == 84
    assert fingerprint(paths) == baseline['asset_tree_sha256']
    raw = [p for p in (ROOT / 'data/knowledge').rglob('*') if p.is_file()]
    assert len(raw) == baseline['knowledge_file_count'] == 917
    assert fingerprint(raw) == baseline['knowledge_tree_sha256']
    assert sha(ROOT / 'web/src/data/lectures.json') == baseline['catalog_sha256']


def test_release_is_only_the_next_small_contiguous_jgy_batch():
    old = RECEIPT['baseline']['video_ids']
    next_episode = 1 + max(int(vid.split('-')[1]) for vid in old if vid.startswith('jgy-'))
    ids = [item['video_id'] for item in BATCH]
    assert ids == [f'jgy-{i:03}' for i in range(next_episode, next_episode + 3)]
    manifest = json.loads((ROOT / 'web/src/data/publish-manifest.json').read_text())
    published = {r['video_id'] for r in manifest['lectures'] if r['has_public_transcript']}
    assert len(manifest['lectures']) == 145
    assert published == set(old) | set(ids)
    for layer in LAYERS:
        assert {p.stem for p in (ROOT / layer).glob('*.json')} == published


def test_new_transcripts_match_audited_source_projections_and_all_four_layers_exist():
    manifest = json.loads((ROOT / 'web/src/data/publish-manifest.json').read_text())
    by_id = {r['video_id']: r for r in manifest['lectures']}
    for receipt in BATCH:
        vid = receipt['video_id']
        path = ROOT / f'web/public/transcripts/{vid}.json'
        assert sha(path) == receipt['projected_transcript_sha256']
        data = json.loads(path.read_text())
        assert data['video_id'] == vid
        rows = data['segments']
        assert len(rows) == receipt['segment_count']
        assert [r['seq'] for r in rows] == list(range(len(rows)))
        assert rows[0]['start_s'] == receipt['first_start_s']
        assert rows[-1]['end_s'] == receipt['last_end_s']
        assert all(rows[i]['start_s'] <= rows[i + 1]['start_s'] for i in range(len(rows) - 1))
        for layer in LAYERS:
            assert (ROOT / layer / f'{vid}.json').is_file()
        assert (ROOT / f'web/src/data/chapters/{vid}.json').read_bytes() == (ROOT / f'data/knowledge/{vid}/chapters.json').read_bytes()
        assert by_id[vid]['has_public_transcript'] and by_id[vid]['has_public_knowledge']


def test_all_new_kp_and_chapter_seq_references_match_actual_transcript_times():
    """Every reference, not merely one chapter/transcript overlap; seconds, no ASR claim."""
    for receipt in BATCH:
        vid = receipt['video_id']
        rows = json.loads((ROOT / f'web/public/transcripts/{vid}.json').read_text())['segments']
        by_seq = {r['seq']: r for r in rows}
        base = ROOT / 'data/knowledge' / vid
        points = [json.loads(line) for line in (base / 'knowledge_points.jsonl').read_text().splitlines() if line.strip()]
        chapters = json.loads((base / 'chapters.json').read_text())
        assert len(points) == receipt['knowledge_point_count']
        assert len(chapters) == receipt['chapter_count']
        for record in points + chapters:
            assert record['video_id'] == vid
            assert record['seg_from'] <= record['seg_to']
            assert record['start_s'] == by_seq[record['seg_from']]['start_s']
            assert record['end_s'] == by_seq[record['seg_to']]['end_s']
