from __future__ import annotations
import logging, sys

def get_logger(name: str = "tcmkb", level: int = logging.INFO) -> logging.Logger:
    log = logging.getLogger(name)
    if not log.handlers:
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s",
                                         datefmt="%Y-%m-%d %H:%M:%S"))
        log.addHandler(h)
        log.setLevel(level)
        log.propagate = False
    return log
