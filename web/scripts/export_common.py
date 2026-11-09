"""Fail-closed export batch: validate selection, stage all outputs, then publish."""
import sys
import tempfile
from pathlib import Path
from publish_manifest import ROOT, read_json, require, validate_payload


def export_batch(ids, source, out, layer, export_one):
    try:
        require(bool(ids) and len(ids) == len(set(ids)), 'ids must be nonempty and unique')
        catalog = {r['id'] for r in read_json(ROOT/'web/src/data/lectures.json')['lectures']}
        require(set(ids) <= catalog, 'ids outside catalog')
        # Same filesystem so each replace is atomic. Input/validation failures write
        # nothing to the destination; an OS failure during final moves is nonzero.
        out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.export-', dir=out.parent) as temp:
            stage = Path(temp)
            for vid in ids:
                require(export_one(vid, source, stage), f'{vid}: input missing')
                validate_payload(vid, layer, read_json(stage/f'{vid}.json'))
            out.mkdir(parents=True, exist_ok=True)
            for vid in ids:
                (stage/f'{vid}.json').replace(out/f'{vid}.json')
        print(f'done: {len(ids)}/{len(ids)} (validated)')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'export failed: {exc}', file=sys.stderr)
        return 1
