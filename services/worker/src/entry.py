"""Cloudflare Workers entry for the 方证图 slice.

Local development stays ``python -m tcmkb_api`` and ``npm run dev`` in ``web/``.
pywrangler deploys this module. ``graph_data`` is generated from the snapshot
so the JSON is imported with the script, not read from the lecture JSONL tree.
"""
from graph_data import GRAPH_SNAPSHOT_JSON
from tcmkb_api.app import create_app
from workers import asgi

# An unbuilt/local entry is honest unknown, not a guessed environment revision.
try:
    from build_info import BUILD_INFO
except ModuleNotFoundError as exc:
    if exc.name != "build_info":
        raise
    BUILD_INFO = None

app = create_app(snapshot_json=GRAPH_SNAPSHOT_JSON, build_info=BUILD_INFO)
Default = asgi.entrypoint(app)
