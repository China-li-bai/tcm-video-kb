"""HTTP surface for the formula-pattern slice.

``GET /health``
``GET /graph/subgraph?focus=formula.gui_zhi_tang``
``GET /graph/paths?focus=formula.gui_zhi_tang``

Local uvicorn (``python -m tcmkb_api``) computes lecture edges with the same hard
gate as ``python -m tcmkb_graph draft``. It does not read a hand-edited JSONL into
the response: a file cannot flip ``review_status`` to ``approved``. The CLI still
writes ``data/graph/candidates.jsonl`` as an audit copy of that same function.

The Cloudflare Worker passes ``snapshot=`` into :func:`create_app`. That file is
produced by ``python -m tcmkb_graph snapshot`` and re-validated on load through
``CandidateEdge``, which rejects ``review_status='approved'``.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from tcmkb_core.config import repo_root

from tcmkb_graph.draft import Materialization, materialize
from tcmkb_graph.subgraph import build_paths, build_subgraph


class GraphService:
    def __init__(
        self,
        root: Path,
        snapshot: Path | None = None,
        snapshot_json: str | None = None,
    ):
        self.root = root
        self.snapshot = snapshot
        self.snapshot_json = snapshot_json
        self._mat: Materialization | None = None

    def mat(self) -> Materialization:
        if self._mat is None:
            if self.snapshot_json is not None:
                from tcmkb_graph.snapshot import loads_snapshot
                self._mat = loads_snapshot(self.snapshot_json, origin=self.root)
            elif self.snapshot is not None:
                from tcmkb_graph.snapshot import load_snapshot
                self._mat = load_snapshot(self.snapshot)
            else:
                self._mat = materialize(self.root)
        return self._mat

    def subgraph(self, focus: str) -> dict:
        try:
            return build_subgraph(focus, self.mat())
        except KeyError:
            raise KeyError(focus) from None

    def paths(self, focus: str) -> dict:
        try:
            return build_paths(focus, self.mat())
        except KeyError:
            raise KeyError(focus) from None


def create_app(
    root: str | Path | None = None,
    *,
    snapshot: str | Path | None = None,
    snapshot_json: str | None = None,
) -> FastAPI:
    if snapshot is not None and snapshot_json is not None:
        raise ValueError("pass snapshot or snapshot_json, not both")
    snap = Path(snapshot) if snapshot is not None else None
    if root is not None:
        root_path = Path(root).resolve()
    elif snap is not None:
        root_path = snap.parent
    else:
        root_path = repo_root()
    service = GraphService(root_path, snapshot=snap, snapshot_json=snapshot_json)
    app = FastAPI(title="tcm-video-kb", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/graph/subgraph")
    def subgraph(focus: str = Query(..., min_length=1)) -> dict:
        try:
            return service.subgraph(focus)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown focus: {focus}") from None

    @app.get("/graph/paths")
    def paths(focus: str = Query(..., min_length=1)) -> dict:
        try:
            return service.paths(focus)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown focus: {focus}") from None

    return app


app = create_app()


def main() -> None:
    import uvicorn
    uvicorn.run("tcmkb_api.app:app", host="127.0.0.1", port=8000, factory=False)
