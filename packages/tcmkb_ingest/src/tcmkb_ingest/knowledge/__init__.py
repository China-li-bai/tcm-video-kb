"""Knowledge layer over transcripts (s09_knowledge).

Deterministic, reusable parts live here (no LLM needed):
  episode.py   load segments / s08 chapters / YouTube source for one video
  chunk.py     time windows over segments + reading text for an annotator
  lexmatch.py  lexicon entity candidates (canonical + aliases + ASR corrections), clause matching
  build.py     annotations -> validated chapters / entities / knowledge points, outline.md
  export.py    aggregated CSV index over all episodes
The semantic part (reading windows and writing annotations/w*.yaml) is done by a reader.
"""
