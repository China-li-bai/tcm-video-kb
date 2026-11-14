#!/usr/bin/env python3
"""Offline QA schema + reference validator. NOT retrieval/model/answer evaluation.

python3 scripts/eval/validate_qa.py --strict-kp --json
No writes, network, models, ASR artifacts, or knowledge-build. JSON goes to stdout;
exit 0=valid structure/references, 1=invalid data, 2=unreadable/missing input.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from decimal import Decimal
import hashlib
import io
import json
import math
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

REPO = Path(__file__).resolve().parents[2]
REQUIRED = ('id', 'question', 'series', 'gold_video_id', 'gold_start_s', 'gold_end_s', 'tolerance_s')
ALLOWED = {*REQUIRED, 'gold_kp_id', 'tags', 'notes'}
VIDEO = re.compile(r'^([a-z][a-z0-9]*)-([0-9]{3,})$')
EPSILON = Decimal('0.05')  # Existing CSV/citation rounding, NOT retrieval tolerance.


class DuplicateKey(ValueError):
    pass


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKey(key)
        result[key] = value
    return result


def _constant(value):
    raise ValueError('nonstandard JSON constant')


def _number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def _close(a, b):
    return abs(Decimal(str(a)) - Decimal(str(b))) <= EPSILON


def _label(path):
    # Default reports are checkout/cwd independent; external fixture labels omit
    # machine-specific prefixes. Hashes identify the bytes, not modification time.
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return '/'.join(path.parts[-2:])


def validate_qa(path: Path, knowledge_root: Path, index_path: Path, *, strict_kp=False, catalog_path: Path | None = None):
    path, knowledge_root, index_path = (Path(p).absolute() for p in (path, knowledge_root, index_path))
    catalog_path = Path(catalog_path or REPO / "web/src/data/lectures.json").absolute()
    errors, inputs = [], {}
    fatal = False
    records = 0

    def issue(file, line, field, code, message, **detail):
        errors.append(dict(file=_label(file), line=line, field=field, code=code, message=message, **detail))

    def read(file):
        nonlocal fatal
        try:
            raw = file.read_bytes()
            inputs[_label(file)] = hashlib.sha256(raw).hexdigest()
            return raw.decode('utf-8')
        except (OSError, UnicodeError) as error:
            missing = isinstance(error, FileNotFoundError)
            fatal = fatal or isinstance(error, OSError)
            inputs[_label(file)] = None
            issue(file, 0, '$', 'missing_input' if missing else 'unreadable_input', 'Required input is missing.' if missing else 'Cannot read UTF-8 input.')
            return None

    def json_rows(file, *, questions=False):
        nonlocal records
        text = read(file)
        if text is None:
            return []
        rows = []
        count = 0
        for line, text in enumerate(text.splitlines(), 1):
            if not text.strip() or text.lstrip().startswith('#'):
                continue
            count += 1
            if questions:
                records += 1
            try:
                value = json.loads(text, object_pairs_hook=_object, parse_constant=_constant)
            except DuplicateKey as error:
                issue(file, line, str(error), 'duplicate_json_key', 'Duplicate JSON object key.')
                continue
            except (ValueError, RecursionError):
                issue(file, line, '$', 'invalid_json', 'Invalid JSON object (nonstandard constants are not allowed).')
                continue
            if not isinstance(value, dict):
                issue(file, line, '$', 'invalid_type', 'Each data line must be an object.')
                continue
            rows.append((line, value))
        if count == 0:
            issue(file, 0, '$', 'empty_dataset' if questions else 'empty_reference', 'No data records; blank/comment-only files do not pass.')
        return rows

    rows = json_rows(path, questions=True)
    if not knowledge_root.is_dir():
        fatal = True
        issue(knowledge_root, 0, '$', 'missing_input', 'Knowledge root directory is missing.')

    catalog = {}
    catalog_text = read(catalog_path)
    if catalog_text is not None:
        try:
            catalog_rows = json.loads(catalog_text, object_pairs_hook=_object, parse_constant=_constant)['lectures']
            if not isinstance(catalog_rows, list) or not catalog_rows:
                raise ValueError('empty catalog')
            for position, lecture in enumerate(catalog_rows):
                vid = lecture.get('id') if isinstance(lecture, dict) else None
                if not isinstance(vid, str) or not VIDEO.fullmatch(vid):
                    issue(catalog_path, 0, f'lectures[{position}].id', 'catalog_identity', 'Invalid catalog lecture ID.')
                elif vid in catalog:
                    issue(catalog_path, 0, f'lectures[{position}].id', 'duplicate_video', 'Duplicate catalog lecture ID.')
                else:
                    catalog[vid] = lecture.get('youtubeId')
        except (ValueError, KeyError, TypeError, RecursionError):
            issue(catalog_path, 0, 'lectures', 'invalid_catalog', 'Cannot parse the catalog lecture list.')

    index, ambiguous = {}, set()
    text = read(index_path)
    if text is not None:
        try:
            reader = csv.DictReader(io.StringIO(text), strict=True)
            required = {'kp_id', 'video_id', 'start_s', 'end_s'}
            headers = reader.fieldnames or []
            if not required <= set(headers) or len(headers) != len(set(headers)):
                issue(index_path, 1, '$', 'index_header', 'Index requires unique kp_id/video_id/start_s/end_s headers.')
            else:
                for row in reader:
                    line = reader.line_num
                    kid, vid = row.get('kp_id'), row.get('video_id')
                    if not isinstance(kid, str) or not isinstance(vid, str) or not VIDEO.fullmatch(vid) or not re.fullmatch(re.escape(vid) + r'\.kp[0-9]+', kid):
                        issue(index_path, line, 'kp_id', 'index_identity', 'Index KP identity must match its lecture.')
                        continue
                    if kid in index or kid in ambiguous:
                        issue(index_path, line, 'kp_id', 'duplicate_kp', 'Duplicate index KP identity; never last-row-wins.')
                        ambiguous.add(kid)
                        continue
                    try:
                        start, end = float(row['start_s']), float(row['end_s'])
                    except (ValueError, TypeError):
                        start = end = float('nan')
                    if not _number(start) or not _number(end) or end < start:
                        issue(index_path, line, 'start_s', 'index_time', 'Index times must be finite nonnegative and ordered.')
                        continue
                    index[kid] = (vid, start, end, line)
                if not index:
                    issue(index_path, 0, '$', 'empty_index', 'No valid index rows.')
        except csv.Error:
            issue(index_path, reader.reader.line_num, '$', 'invalid_csv', 'Cannot parse reference index CSV.')

    native_cache = {}

    def native(vid):
        if vid not in native_cache:
            file = knowledge_root / vid / 'knowledge_points.jsonl'
            points, duplicates = {}, set()
            source_error_count = len(errors)
            if not file.resolve().is_relative_to(knowledge_root.resolve()):
                issue(file, 0, '$', 'unsafe_reference', 'Reference file escapes knowledge root.')
            else:
                for line, kp in json_rows(file):
                    kid = kp.get('kp_id')
                    if not isinstance(kid, str):
                        issue(file, line, 'kp_id', 'invalid_type', 'Native KP needs a string identity.')
                        continue
                    if kid in points:
                        duplicates.add(kid)
                        issue(file, line, 'kp_id', 'duplicate_kp', 'Duplicate native KP identity.')
                    else:
                        points[kid] = (line, kp)
            native_cache[vid] = (file, points, duplicates, len(errors) == source_error_count)
        return native_cache[vid]

    seen, series, referenced, lectures = set(), Counter(), [], set()
    valid = video_only = 0
    for line, row in rows:
        before = len(errors)
        for field in sorted(row.keys() - ALLOWED):
            issue(path, line, field, 'unknown_field', 'Unknown field; this schema has one optional scalar gold_kp_id, not multiple references.')
        for field in REQUIRED:
            if field not in row:
                issue(path, line, field, 'required', 'Required field is missing.')
        for field in ('id', 'question', 'series', 'gold_video_id'):
            if field in row and (not isinstance(row[field], str) or not row[field].strip()):
                issue(path, line, field, 'invalid_type', 'Expected a nonblank string.')
        rid = row.get('id')
        if isinstance(rid, str) and rid.strip():
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', rid):
                issue(path, line, 'id', 'invalid_id', 'ID must be a short stable ASCII identifier.')
            if rid in seen:
                issue(path, line, 'id', 'duplicate_id', 'Question ID is duplicated.')
            seen.add(rid)
        for field in ('gold_start_s', 'gold_end_s', 'tolerance_s'):
            if field in row and not _number(row[field]):
                issue(path, line, field, 'invalid_number', 'Expected a finite nonnegative JSON number, not bool/string/null.')
        start, end = row.get('gold_start_s'), row.get('gold_end_s')
        if _number(start) and _number(end) and end < start:
            issue(path, line, 'gold_end_s', 'time_order', 'End precedes start.')
        if 'tags' in row and (not isinstance(row['tags'], list) or any(not isinstance(t, str) or not t.strip() for t in row['tags'])):
            issue(path, line, 'tags', 'invalid_type', 'Tags must be a list of nonblank strings.')
        if 'notes' in row and not isinstance(row['notes'], str):
            issue(path, line, 'notes', 'invalid_type', 'Notes must be a string.')
        vid, kid = row.get('gold_video_id'), row.get('gold_kp_id')
        match = VIDEO.fullmatch(vid) if isinstance(vid, str) else None
        if isinstance(vid, str) and not match:
            issue(path, line, 'gold_video_id', 'invalid_id', 'Lecture ID must be a safe series-NNN identity.')
        if match:
            folder = knowledge_root / vid
            if vid not in catalog or not folder.is_dir() or not folder.resolve().is_relative_to(knowledge_root.resolve()):
                issue(path, line, 'gold_video_id', 'missing_lecture', 'Lecture is absent from catalog/knowledge or escapes knowledge root.')
        if match and row.get('series') != match[1]:
            issue(path, line, 'series', 'series_mismatch', 'Series disagrees with gold_video_id.')
        if kid is None and strict_kp:
            issue(path, line, 'gold_kp_id', 'required', 'Strict mode requires a scalar KP reference.')
        elif kid is not None and (not isinstance(kid, str) or not match or not re.fullmatch(re.escape(vid) + r'\.kp[0-9]+', kid)):
            issue(path, line, 'gold_kp_id', 'invalid_id', 'KP ID must be one string in the same lecture.')
        if len(errors) != before:
            continue
        lectures.add(vid)
        series[row['series']] += 1
        if kid is None:
            video_only += 1
            valid += 1
            continue
        referenced.append(kid)
        indexed = index.get(kid)
        if indexed is None or kid in ambiguous:
            issue(path, line, 'gold_kp_id', 'index_reference', 'KP is missing/ambiguous in the knowledge index.')
            continue
        if indexed[0] != vid:
            issue(path, line, 'gold_kp_id', 'index_video', 'Index KP belongs to a different lecture.')
        for field, target in (('gold_start_s', indexed[1]), ('gold_end_s', indexed[2])):
            if not _close(row[field], target):
                issue(path, line, field, 'index_time_mismatch', 'Gold time differs from index by more than 0.05 seconds.')
        file, points, duplicates, healthy = native(vid)
        if not healthy:
            issue(path, line, 'gold_kp_id', 'invalid_native_input', 'Referenced native JSONL is not valid.',
                  reference_file=_label(file), reference_line=0, reference_field='$')
        if kid not in points or kid in duplicates:
            issue(path, line, 'gold_kp_id', 'native_reference', 'KP is missing/ambiguous in canonical JSONL.', reference_file=_label(file))
            continue
        source_line, kp = points[kid]

        def ref_error(field, code, message):
            issue(path, line, 'gold_kp_id', code, message, reference_file=_label(file), reference_line=source_line, reference_field=field)

        if kp.get('video_id') != vid:
            ref_error('video_id', 'kp_video_mismatch', 'Canonical KP lecture disagrees with the question.')
        times = all(_number(kp.get(f)) for f in ('start_s', 'end_s'))
        if not times or kp['end_s'] < kp['start_s']:
            ref_error('start_s/end_s', 'kp_time', 'Canonical KP times are invalid.')
        else:
            for field, source in (('gold_start_s', 'start_s'), ('gold_end_s', 'end_s')):
                if not _close(row[field], kp[source]) or not _close(indexed[1 if source == 'start_s' else 2], kp[source]):
                    issue(path, line, field, 'native_time_mismatch', 'Gold/index time disagrees with canonical KP beyond 0.05 seconds.', reference_file=_label(file), reference_line=source_line, reference_field=source)
        cite = kp.get('citation')
        if not isinstance(cite, dict):
            ref_error('citation', 'missing_citation', 'Canonical KP source citation is missing.')
        else:
            if cite.get('series') != match[1] or type(cite.get('episode')) is not int or cite['episode'] != int(match[2]):
                ref_error('citation.series/episode', 'citation_identity', 'Source citation disagrees with the lecture identity.')
            if not all(_number(cite.get(f)) for f in ('start_s', 'end_s')) or cite['end_s'] < cite['start_s']:
                ref_error('citation.start_s/end_s', 'citation_time', 'Source citation times are invalid.')
            elif times and any(not _close(cite[f], kp[f]) for f in ('start_s', 'end_s')):
                ref_error('citation.start_s/end_s', 'citation_time', 'Source citation disagrees with canonical time beyond rounding allowance.')
            yt = cite.get('youtube_id')
            if yt != catalog.get(vid):
                ref_error('citation.youtube_id', 'catalog_source', 'Canonical citation YouTube identity disagrees with the lecture catalog.')
            try:
                url = urlsplit(cite.get('url', ''))
                query = parse_qs(url.query, keep_blank_values=True)
                ids = query.get('v', [])
                source = url.path[1:] if url.hostname == 'youtu.be' else ids[0] if url.hostname in ('youtube.com','www.youtube.com','m.youtube.com') and url.path == '/watch' and len(ids) == 1 else None
                safe = url.scheme == 'https' and not url.username and not url.password and url.port in (None, 443)
                if not isinstance(yt, str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}', yt) or not safe or source != yt:
                    raise ValueError('source identity')
                for parameter in ('t', 'start'):
                    if parameter not in query:
                        continue
                    values = query[parameter]
                    if len(values) != 1 or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?s?', values[0]):
                        raise ValueError('ambiguous/invalid source seconds')
                    seconds = float(values[0].removesuffix('s'))
                    targets = [kp.get('start_s'), cite.get('start_s')]
                    if not _number(seconds) or not any(_number(t) and math.floor(seconds) == math.floor(t) for t in targets):
                        raise ValueError('source seconds mismatch')
            except (TypeError, ValueError, AttributeError):
                ref_error('citation.url/youtube_id', 'citation_source', 'Expected matching HTTPS YouTube identity and unambiguous source seconds; no URL is fetched.')
        if len(errors) == before:
            valid += 1

    errors.sort(key=lambda e: (e['file'], e['line'], e['field'], e['code']))
    return dict(schema='qa-validation/1', scope='schema_and_references', answer_quality='not_evaluated', retrieval_metrics=None,
                strict_kp=bool(strict_kp), ok=not errors, exit_code=2 if fatal else 1 if errors else 0,
                counts=dict(records=records, valid_records=valid, invalid_records=records-valid, errors=len(errors),
                            kp_references=len(referenced), unique_kps=len(set(referenced)), video_only_references=video_only, lectures=len(lectures)),
                series=dict(sorted(series.items())), inputs=[dict(path=p, sha256=h) for p, h in sorted(inputs.items())], errors=errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', type=Path, default=Path('eval/retrieval/qa.jsonl'))
    parser.add_argument('--knowledge-root', type=Path, default=Path('data/knowledge'))
    parser.add_argument('--index', type=Path, default=Path('data/knowledge/_index/knowledge_points.csv'))
    parser.add_argument('--catalog', type=Path, default=Path('web/src/data/lectures.json'))
    parser.add_argument('--strict-kp', action='store_true', help='require a scalar gold_kp_id on every question (CI mode)')
    parser.add_argument('--json', action='store_true', help='stable qa-validation/1 report on stdout')
    args = parser.parse_args()
    rooted = lambda p: p if p.is_absolute() else REPO / p
    report = validate_qa(rooted(args.path), rooted(args.knowledge_root), rooted(args.index), strict_kp=args.strict_kp, catalog_path=rooted(args.catalog))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    else:
        print(f"{'OK' if report['ok'] else 'FAIL'} {_label(rooted(args.path))}: {report['counts']['valid_records']}/{report['counts']['records']} records; {report['counts']['errors']} errors; schema/references ONLY, answer quality NOT evaluated")
        for error in report['errors']:
            reference = f" -> {error['reference_file']}:{error.get('reference_line', 0)}:{error.get('reference_field', '$')}" if 'reference_file' in error else ''
            print(f"  {error['file']}:{error['line']}:{error['field']} [{error['code']}] {error['message']}{reference}")
    return report['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
