"""tcmkb_lexicon — shared TCM lexicon tooling (see docs/ARCHITECTURE.md §7).
correct/match have no third-party deps, so ASR workers can import them without yaml/jsonschema."""
from .correct import Corrector
from .match import Matcher

def __getattr__(name):
    if name in ("Lexicon", "load_lexicon"):
        from . import load
        return getattr(load, name)
    raise AttributeError(name)
__all__ = ["Lexicon", "load_lexicon", "Corrector", "Matcher"]
