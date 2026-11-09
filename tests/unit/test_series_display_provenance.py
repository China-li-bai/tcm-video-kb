"""PR12 uses retained source evidence, never a guess from the nj abbreviation."""
import json
import re
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_nj_display_name_is_supported_by_retained_independent_source_fields():
    series = yaml.safe_load((ROOT / 'configs/series.yaml').read_text())['series']
    source = next(s for s in series if s['series_id'] == 'nj')
    inventory = yaml.safe_load((ROOT / 'configs/sources/youtube_renji.yaml').read_text())['series']['nj']
    rows = [r for r in json.loads((ROOT / 'web/src/data/lectures.json').read_text())['lectures'] if r['series'] == 'nj']
    assert source['title'] == inventory['title'] == '黄帝内经'
    assert source['book_id'] == 'huangdineijing'
    assert len(rows) == inventory['best']['videos'] == 10
    assert all(re.findall('《([^》]+)》', r['title']) == [source['title']] for r in rows)
    # Old display mistakes remain an auditable raw snapshot, not a search alias.
    assert {r['seriesLabel'] for r in rows} == {'难经'}
    assert [r['id'] for r in rows] == [f'nj-{i:03}' for i in range(1, 11)]


def test_production_catalog_consumers_share_one_display_read_boundary():
    readers = []
    for file in (ROOT / 'web/src').rglob('*'):
        if file.suffix not in {'.ts', '.tsx'} or '.test.' in file.name:
            continue
        if re.search(r'from [\"\'][^\"\']*data/lectures\.json[\"\']', file.read_text()):
            readers.append(file.relative_to(ROOT / 'web/src').as_posix())
    assert sorted(readers) == ['listen/lectures.ts'], 'UI must not bypass the source-backed display projection'
