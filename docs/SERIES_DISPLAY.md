# PR-12: source-backed series display alignment

## Decision and evidence (repository evidence, not a new online verification)

The displayed series name for the existing ten `nj-001`…`nj-010` lectures is
**黄帝内经**. This is not inferred from the abbreviation `nj`:

- `configs/series.yaml:12-16` already assigns this series `title: 黄帝内经` and
  `book_id: huangdineijing`.
- `configs/sources/youtube_renji.yaml:39-54` already names the ten-video source
  inventory 黄帝内经, retaining its playlist/channel references. Its historical
  probe/comment is a repository record, not a probe performed in this PR.
- All ten original `web/src/data/lectures.json` titles explicitly contain
  `《黄帝内经》` (first: `01 倪海厦精讲《黄帝内经》高清字幕完整版`; last:
  `10 倪海厦精讲《黄帝内经》高清字幕完整版 完结`). Original YouTube IDs stay intact.

These independent retained fields agree; the old `seriesLabel: 难经` and the
old「难经脉络：脉诊与脏腑」blurb disagree. Lexicon entries mentioning 难经 are
actual vocabulary, not evidence that this particular series has that name.
They are not renamed or removed. This PR does not authenticate reuploads,
content correctness, rights, completeness or actual video availability.

## Small display-only correction; no source migration

The original proposal suggested editing catalog labels and one blurb. This
implementation instead projects **only the display `seriesLabel`** at the existing
`web/src/listen/lectures.ts` read boundary and changes its one plain-language blurb
to「黄帝内经：按原讲次标题，逐集听原讲。」. No extra teaching-content claim.

Why: retained catalog/source fields and historical release byte-hash checks stay
unchanged, auditable and reproducible. The raw catalog's old `seriesLabel` is a
historical UI mistake, **not a claim that the original platform called it 难经**.
The projection does not mutate it. No metadata/public asset is regenerated.

All production consumers share that one display boundary. The legacy
`LecturesPage` previously imported the raw catalog directly; it now uses the
same reader instead of retaining a competing label/filter mapping. Existing
series list/detail, search/hit snippets, Watch breadcrumb, Stash and Recall
already use that reader. Homepage resume keeps its original stored source title;
its normal today's/up-next shl selection is not changed or mocked into nj.

- Stable `series`, `video_id`, routes `/series/nj`, `/watch/nj-NNN`, `?t=`,
  original titles/YouTube IDs/durations/chapter metadata remain unchanged.
- Existing stash IDs, personal saved titles (even old wording) and raw stored
  bytes are not migrated. Opening a Watch route may still update its existing
  last-request key normally; that is not playback telemetry.
- Search continues matching actual source titles, canonical display names and
  stable IDs. **No 难经 alias is added**: there is no evidence it is a correct
  alternate series name. Genuine source/quote/vocabulary mentions remain searchable
  through existing mechanisms; they are not globally suppressed.
- Relabelling does not publish transcripts: these ten nj lectures remain outside
  the published24 transcript episodes, with the existing honest missing-text UI.
- No CSS/layout/player strategy, source/knowledge/QA/catalog/chapters/graph/public
  assets, dependencies, CI configuration, account or backend changes.

## Tests, limits and rollback

`tests/unit/test_series_display_provenance.py` reads the retained source fields,
all ten titles and IDs, and prevents UI bypass of the single display reader.
`web/src/listen/seriesDisplay.test.tsx` checks all145 rows' preservation (only ten
runtime labels differ), search identity/aliases, real series/detail/Watch breadcrumb,
legacy catalog filtering/source URLs, search form/navigation, homepage old request,
and historical Stash→Recall→source routes with raw storage preservation.
Only external HTTP and missing DOM APIs are replaced; real components, effects,
router, search and read/projection logic run. No real private user file is used.

See [TESTING.md](TESTING.md) for genuine RED, corrected test assumptions and
full local240 Python/201 frontend/16 publish results. Remote job evidence lives
in this PR and the main Page after actual completion, not inferred from local green.

jsdom does **not** verify browser/mobile geometry, file download delivery,
YouTube playback or cross-origin behavior. Browser403 and those independent
premerge gates remain unverified, without preview/network retries or bypass.

Base `test/qa-reference-validation@6776f04`, depends on #23. Original plan PR-12
only; PR-8 remains condition-deferred and PR-9 prerequisite-blocked. No main merge,
deployment or next development task. Ordinary revert restores old display code;
no data/storage migration or rollback script. If future source evidence changes,
review the display mapping/tests explicitly; never derive a new book name from
an abbreviation or silently rewrite original titles.
