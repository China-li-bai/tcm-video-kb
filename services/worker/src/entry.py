"""Cloudflare Workers entry for the 方证图 slice.

Local development stays ``python -m tcmkb_api`` and ``npm run dev`` in ``web/``.
pywrangler deploys this module. ``graph_data`` is generated from the snapshot
so the JSON is imported with the script, not read from the lecture JSONL tree.
"""
from graph_data import GRAPH_SNAPSHOT_JSON
from tcmkb_api.app import create_app
from workers import asgi

app = create_app(snapshot_json=GRAPH_SNAPSHOT_JSON)
Default = asgi.entrypoint(app)
