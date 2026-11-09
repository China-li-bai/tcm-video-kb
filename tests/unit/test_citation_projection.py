"""Read/export projection contracts. Never rewrite tracked knowledge or publication assets."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
from tcmkb_core.config import repo_root
from tcmkb_core.knowledge import KCitation, KnowledgePoint, KChapter
from tcmkb_core.play import site_watch_url
from tcmkb_ingest.knowledge.export import build_index

ROOT = repo_root()
VECTORS = json.loads((ROOT / 'tests/fixtures/citation-links.json').read_text())


@pytest.mark.parametrize('case', VECTORS)
def test_shared_site_link_contract(case, monkeypatch):
    monkeypatch.delenv('TCMKB_SITE_BASE', raising=False)
    assert site_watch_url(case['id'], case.get('t')) == case['href']


@pytest.mark.parametrize('seconds', [float('nan'), float('inf'), -float('inf')])
def test_nonfinite_time_is_not_a_zero_time_citation(seconds):
    assert site_watch_url('shl-001', seconds) is None


def legacy(**extra):
    return dict(youtube_id='W-z7WGZXmp8', url='https://youtu.be/W-z7WGZXmp8?t=125',
                series='shl', episode=1, title='原讲', start_s=125.99, end_s=130, **extra)


def test_legacy_projection_derives_canonical_links_without_mutating_source():
    raw = legacy(t_url='https://evil.test/steal', youtube_t_url='javascript:alert(1)')
    before = json.dumps(raw, sort_keys=True)
    cite = KCitation.from_legacy(raw, video_id='shl-001')
    assert cite.video_id == 'shl-001'
    assert cite.t_url == '/watch/shl-001?t=125'
    assert cite.youtube_t_url == 'https://www.youtube.com/watch?v=W-z7WGZXmp8&t=125s'
    assert cite.url == raw['url'], 'preserve original provenance; do not use it as an unchecked link'
    assert json.dumps(raw, sort_keys=True) == before


@pytest.mark.parametrize('bad', ['', '../x', 'shl-001?next=x', None])
def test_legacy_projection_requires_valid_authoritative_video(bad):
    with pytest.raises(ValueError):
        KCitation.from_legacy(legacy(), video_id=bad)


def test_legacy_projection_rejects_conflicting_identity():
    with pytest.raises(ValueError, match='video_id'):
        KCitation.from_legacy(legacy(video_id='shl-002'), video_id='shl-001')


@pytest.mark.parametrize('time', [None, 'bad', True, float('nan'), float('inf')])
def test_legacy_projection_rejects_imprecise_times(time):
    raw = legacy(); raw['start_s'] = time
    with pytest.raises(ValueError):
        KCitation.from_legacy(raw, video_id='shl-001')


def test_legacy_url_only_youtube_and_missing_source():
    raw = legacy(); raw.pop('youtube_id')
    assert KCitation.from_legacy(raw, video_id='shl-001').youtube_t_url.endswith('&t=125s')
    raw['url'] = 'https://youtube.com.evil.test/watch?v=BAD'
    assert KCitation.from_legacy(raw, video_id='shl-001').youtube_t_url is None
    raw.pop('url')
    assert KCitation.from_legacy(raw, video_id='shl-001').t_url == '/watch/shl-001?t=125'


def test_all_historical_citations_and_real_csv_projection_are_read_only(tmp_path):
    protected = sorted((ROOT/'data/knowledge').rglob('*')) + sorted((ROOT/'web/public').rglob('*.json')) + sorted((ROOT/'web/src/data').rglob('*.json'))
    protected = [p for p in protected if p.is_file()]
    digest = lambda: {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    before = digest()
    n_points = n_chapters = 0
    for directory in sorted((ROOT/'data/knowledge').iterdir()):
        if not (directory/'knowledge_points.jsonl').is_file(): continue
        for line in (directory/'knowledge_points.jsonl').read_text().splitlines():
            if not line.strip(): continue
            row = json.loads(line)
            assert 't_url' not in row['citation'], 'migration is a read projection, not a raw-data rewrite'
            cite = KCitation.from_legacy(row['citation'], video_id=row['video_id'])
            assert cite.t_url == site_watch_url(row['video_id'], row['citation']['start_s'])
            assert cite.youtube_t_url.startswith('https://www.youtube.com/watch?v=')
            projected = KCitation.from_record(row)
            assert KnowledgePoint.model_validate(row).citation == projected
            assert projected.start_s == row['start_s'] and projected.t_url == site_watch_url(row['video_id'], row['start_s'])
            n_points += 1
        for row in json.loads((directory/'chapters.json').read_text()):
            cite = KCitation.from_legacy(row['citation'], video_id=row['video_id'])
            assert cite.t_url == site_watch_url(row['video_id'], row['citation']['start_s'])
            assert KChapter.model_validate(row).citation.t_url == site_watch_url(row['video_id'], row['start_s'])
            n_chapters += 1
    assert n_points == 1575 and n_chapters > 0
    output = tmp_path/'index'
    report = build_index(ROOT, out=output)
    assert report['n_knowledge_points'] == n_points
    assert report['n_chapters'] == n_chapters
    for name in ('knowledge_points.csv', 'chapters.csv'):
        rows = list(csv.DictReader((output/name).open()))
        assert rows
        assert all(r['url'].startswith(f"/watch/{r['video_id']}") for r in rows)
        assert all(r['youtube_t_url'].startswith('https://www.youtube.com/watch?v=') for r in rows)
    build_index(ROOT, out=tmp_path/'again')
    for name in ('knowledge_points.csv', 'chapters.csv', 'entities.csv', 'index_report.json'):
        assert (output/name).read_bytes() == (tmp_path/'again'/name).read_bytes()
    assert digest() == before, 'all historical JSON/JSONL/CSV and all public JSON must remain byte-identical'


def test_knowledge_record_model_read_projects_legacy_nested_citation():
    from tcmkb_core.knowledge import KnowledgePoint, KChapter
    point = json.loads(next((ROOT/'data/knowledge/shl-001/knowledge_points.jsonl').open()))
    chapter = json.loads((ROOT/'data/knowledge/shl-001/chapters.json').read_text())[0]
    for cls, row in [(KnowledgePoint, point), (KChapter, chapter)]:
        before = json.dumps(row, sort_keys=True)
        record = cls.model_validate(row)
        assert record.citation.video_id == row['video_id']
        assert record.citation.t_url.startswith('/watch/shl-001')
        assert json.dumps(row, sort_keys=True) == before


@pytest.mark.parametrize('seconds', [0, -1.2, 0.99, 125.99])
def test_legacy_numeric_boundaries_and_copy_stability(seconds):
    raw = legacy(); raw['start_s'] = seconds
    cite = KCitation.from_legacy(raw, video_id='shl-001')
    assert cite.start_s == max(seconds, 0)
    assert cite.t_url == site_watch_url('shl-001', seconds)
    assert KCitation.from_legacy(cite.model_dump(), video_id='shl-001') == cite


@pytest.mark.parametrize('seconds', [None, float('nan'), float('inf'), -1])
def test_legacy_invalid_or_reversed_end_is_rejected(seconds):
    raw = legacy(); raw['end_s'] = seconds
    with pytest.raises(ValueError):
        KCitation.from_legacy(raw, video_id='shl-001')


@pytest.mark.parametrize('seconds', [float('nan'), float('inf'), -float('inf')])
def test_graph_citation_model_rejects_nonfinite_seconds(seconds):
    from tcmkb_graph.models import LectureCitation
    with pytest.raises(ValueError):
        LectureCitation(video_id='shl-001', start_s=seconds, end_s=130)


def test_record_times_are_authoritative_over_historical_rounded_citation_times():
    row = {'video_id':'shl-001','start_s':125.999,'end_s':130.001,
           'citation':legacy()}
    row['citation']['start_s'] = 126.0
    cite = KCitation.from_record(row)
    assert cite.start_s == 125.999 and cite.end_s == 130.001
    assert cite.t_url == '/watch/shl-001?t=125'
    assert row['citation']['start_s'] == 126.0


def test_actual_index_cli_bad_citations_fail_nonzero_without_replacing_existing_outputs(tmp_path):
    """Only the file-only index command, never knowledge-build or a model call."""
    from click.testing import CliRunner
    from tcmkb_ingest.cli import main
    directory = tmp_path/'data/knowledge/shl-001'
    directory.mkdir(parents=True)
    (directory/'chapters.json').write_text('[]')
    output = tmp_path/'data/knowledge/_index'
    output.mkdir()
    names = ('knowledge_points.csv', 'chapters.csv', 'entities.csv', 'index_report.json')
    for name in names: (output/name).write_bytes(b'prior-derived-output\n')
    point = dict(kp_id='shl-001.kp0001', video_id='shl-001', type='clinical_tip',
                 entity_ids=[], statement='测试主张', start_s=125.99, end_s=130, citation=legacy())
    for bad in [{**point, 'start_s':None}, {**point, 'citation':legacy(video_id='shl-002')}]:
        (directory/'knowledge_points.jsonl').write_text(json.dumps(bad)+'\n')
        result = CliRunner().invoke(main, ['--root', str(tmp_path), 'knowledge-index'])
        assert result.exit_code != 0 and isinstance(result.exception, ValueError)
        assert all((output/name).read_bytes() == b'prior-derived-output\n' for name in names)
