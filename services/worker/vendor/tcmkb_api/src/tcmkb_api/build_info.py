"""Allowlisted build identity, injected once; never inspect git/env at request time."""
from __future__ import annotations

import re

SCHEMA = 'tcm-build/1'


def normalize_build_info(value: object = None) -> dict:
    result = {'git_sha': 'unknown', 'git_dirty': None, 'content_revision': 'unknown'}
    if not isinstance(value, dict) or value.get('schema') != SCHEMA:
        return result
    sha = value.get('git_sha')
    if isinstance(sha, str) and re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', sha):
        result['git_sha'] = sha
        dirty = value.get('git_dirty')
        if type(dirty) is bool:
            result['git_dirty'] = dirty
    revision = value.get('content_revision')
    if isinstance(revision, str) and re.fullmatch(r'[0-9a-f]{64}', revision):
        result['content_revision'] = revision
    return result
