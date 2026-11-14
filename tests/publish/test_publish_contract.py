"""Real CLI/file contract tests; no artifacts, ingest, or network required."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'web/scripts/publish_manifest.py'


def run(*args):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False))


class PublishContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vid = 'shl-001'
        self.segment = dict(seq=0, start_s=1, end_s=3, text='原句')
        write(self.root/'web/src/data/lectures.json', {'lectures': [dict(id=self.vid, series='shl', youtubeId='abc'), dict(id='zj-002', series='zj', youtubeId='def')]})
        for folder, key, rows in [('transcripts', 'segments', [self.segment]), ('knowledge', 'points', []), ('entities', 'mentions', [])]:
            write(self.root/f'web/public/{folder}/{self.vid}.json', dict(video_id=self.vid, **{key: rows}))
        write(self.root/f'web/src/data/chapters/{self.vid}.json', [dict(video_id=self.vid, chapter_id=self.vid+'.c01', start_s=1, end_s=3)])

    def generate(self, *args):
        return run(SCRIPT, '--root', self.root, *args)

    def test_generation_repeatable_and_optional_layers_honest(self):
        first = self.generate(); self.assertEqual(first.returncode, 0, first.stderr)
        manifest = self.root/'web/src/data/publish-manifest.json'
        before = manifest.read_bytes()
        self.assertEqual(self.generate().returncode, 0)
        self.assertEqual(manifest.read_bytes(), before)
        self.assertEqual(self.generate('--check').returncode, 0)
        rows = json.loads(before)['lectures']
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]['has_public_transcript'])
        self.assertFalse(rows[1]['has_public_transcript'])
        self.assertFalse(rows[1]['has_knowledge'])
        self.assertEqual(rows[1]['playback'], 'youtube')

    def test_missing_companion_fails_without_overwriting_manifest(self):
        self.assertEqual(self.generate().returncode, 0)
        manifest = self.root/'web/src/data/publish-manifest.json'
        before = manifest.read_bytes()
        (self.root/f'web/public/entities/{self.vid}.json').unlink()
        self.assertNotEqual(self.generate().returncode, 0)
        self.assertEqual(manifest.read_bytes(), before)

    def test_duplicate_seq_wrong_id_bad_time_or_empty_text_fail(self):
        path = self.root/f'web/public/transcripts/{self.vid}.json'
        cases = [dict(video_id=self.vid, segments=[self.segment, self.segment]),
                 dict(video_id='zj-002', segments=[self.segment]),
                 dict(video_id=self.vid, segments=[{**self.segment, 'end_s': 0}]),
                 dict(video_id=self.vid, segments=[{**self.segment, 'text': ''}])]
        for case in cases:
            with self.subTest(case=case):
                write(path, case)
                self.assertNotEqual(self.generate().returncode, 0)

    def test_duplicate_catalog_and_unknown_asset_fail(self):
        path = self.root/'web/src/data/lectures.json'
        catalog = json.loads(path.read_text()); catalog['lectures'].append(catalog['lectures'][0]); write(path, catalog)
        self.assertNotEqual(self.generate().returncode, 0)
        catalog['lectures'].pop(); write(path, catalog)
        write(self.root/'web/public/transcripts/no-such-id.json', dict(video_id='no-such-id', segments=[self.segment]))
        self.assertNotEqual(self.generate().returncode, 0)

    def test_no_time_overlap_fails(self):
        write(self.root/f'web/src/data/chapters/{self.vid}.json', [dict(video_id=self.vid, chapter_id=self.vid+'.c01', start_s=50, end_s=60)])
        self.assertNotEqual(self.generate().returncode, 0)

    def test_stale_manifest_fails_check(self):
        self.assertEqual(self.generate().returncode, 0)
        self.segment['text'] = '已变动'
        write(self.root/f'web/public/transcripts/{self.vid}.json', dict(video_id=self.vid, segments=[self.segment]))
        self.assertNotEqual(self.generate('--check').returncode, 0)

    def test_real_repository_coverage(self):
        result = run(SCRIPT, '--check'); self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads((ROOT/'web/src/data/publish-manifest.json').read_text())['lectures']
        self.assertEqual(len(rows), 145)
        ids = {r['video_id'] for r in rows if r['has_public_transcript']}
        self.assertEqual(ids, {p.stem for p in (ROOT/'web/public/transcripts').glob('*.json')})
        self.assertEqual(len(ids), 21)
        self.assertEqual(next(r for r in rows if r['video_id']=='shl-001')['segment_count'], 3604)

    def test_export_missing_inputs_and_duplicate_ids_exit_nonzero(self):
        for script, flag in [('export_transcripts.py', '--artifacts'), ('export_knowledge_points.py', '--knowledge'), ('export_entities.py', '--knowledge')]:
            for ids in [[self.vid], [self.vid, self.vid], []]:
                with self.subTest(script=script, ids=ids):
                    result = run(ROOT/'web/scripts'/script, flag, self.root/'absent', '--out', self.root/'out', '--ids', *ids)
                    self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_export_batch_failure_does_not_publish_partial_files(self):
        src = self.root/self.vid/'segments.jsonl'; src.parent.mkdir()
        src.write_text(json.dumps(self.segment)+'\n')
        result = run(ROOT/'web/scripts/export_transcripts.py', '--artifacts', self.root, '--out', self.root/'out', '--ids', self.vid, 'shl-002')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root/'out'/f'{self.vid}.json').exists())

    def test_export_invalid_transcript_rows_fail_not_skip(self):
        src = self.root/self.vid/'segments.jsonl'; src.parent.mkdir()
        for rows in [[{**self.segment, 'text': ''}], [self.segment, self.segment], [{**self.segment, 'end_s': -1}]]:
            src.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            result = run(ROOT/'web/scripts/export_transcripts.py', '--artifacts', self.root, '--out', self.root/'out', '--ids', self.vid)
            self.assertNotEqual(result.returncode, 0)

    def test_eligible_entity_with_missing_identity_fails(self):
        src = self.root/self.vid/'entities.jsonl'; src.parent.mkdir()
        src.write_text(json.dumps(dict(in_lexicon=True, type='formula', canonical='桂枝汤', mentions=[]))+'\n')
        result = run(ROOT/'web/scripts/export_entities.py', '--knowledge', self.root, '--out', self.root/'out', '--ids', self.vid)
        self.assertNotEqual(result.returncode, 0)

    def test_invalid_knowledge_point_fails_and_empty_entities_are_valid(self):
        base = self.root/self.vid; base.mkdir()
        (base/'knowledge_points.jsonl').write_text(json.dumps(dict(video_id=self.vid, statement='', start_s=2, end_s=1))+'\n')
        result = run(ROOT/'web/scripts/export_knowledge_points.py', '--knowledge', self.root, '--out', self.root/'out', '--ids', self.vid)
        self.assertNotEqual(result.returncode, 0)
        # An intentionally filtered-out draft is not a missing/corrupt source.
        (base/'entities.jsonl').write_text(json.dumps(dict(in_lexicon=False, entity_id='new.formula.test'))+'\n')
        result = run(ROOT/'web/scripts/export_entities.py', '--knowledge', self.root, '--out', self.root/'out', '--ids', self.vid)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.root/'out'/f'{self.vid}.json').read_text())['mentions'], [])

    def test_transcript_roundtrip_preserves_all_shipped_bytes(self):
        # Reconstruct temporary source lines from committed public data. This is
        # only a deterministic exporter fixture, not a claim of local artifacts.
        for src in (ROOT/'web/public/transcripts').glob('*.json'):
            rows = json.loads(src.read_text())['segments']
            dest = self.root/'artifacts'/src.stem/'segments.jsonl'
            dest.parent.mkdir(parents=True)
            dest.write_text(''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in rows))
        result = run(ROOT/'web/scripts/export_transcripts.py', '--artifacts', self.root/'artifacts', '--out', self.root/'transcripts')
        self.assertEqual(result.returncode, 0, result.stderr)
        for src in (ROOT/'web/public/transcripts').glob('*.json'):
            self.assertEqual(src.read_bytes(), (self.root/'transcripts'/src.name).read_bytes())

    def test_real_knowledge_exports_preserve_public_bytes(self):
        for script, folder in [('export_knowledge_points.py', 'knowledge'), ('export_entities.py', 'entities')]:
            result = run(ROOT/'web/scripts'/script, '--out', self.root/folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            for src in (ROOT/f'web/public/{folder}').glob('*.json'):
                self.assertEqual(src.read_bytes(), (self.root/folder/src.name).read_bytes())


if __name__ == '__main__':
    unittest.main()
