"""HTTP surface for the formula-pattern slice.

``GET /health``
``GET /graph/subgraph?focus=formula.gui_zhi_tang``
``GET /graph/paths?focus=formula.gui_zhi_tang``

Lecture edges are computed with the same hard gate as ``python -m tcmkb_graph draft``.
The process does not read a hand-edited JSONL into the response: a file cannot flip
``review_status`` to ``approved``. The CLI still writes ``data/graph/candidates.jsonl``
as an audit copy of that same function.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from tcmkb_core.config import repo_root

from tcmkb_graph.draft import Materialization, materialize
from tcmkb_graph.subgraph import build_paths, build_subgraph


class GraphService:
    def __init__(self, root: Path):
        self.root = root
        self._mat: Materialization | None = None

    def mat(self) -> Materialization:
        if self._mat is None:
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


def create_app(root: str | Path | None = None) -> FastAPI:
    root_path = Path(root).resolve() if root else repo_root()
    service = GraphService(root_path)
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
