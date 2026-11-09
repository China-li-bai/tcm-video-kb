# QA schema and reference gate — original plan PR-11

**This is not retrieval evaluation, model scoring, answer verification or medical
quality assessment.** It runs no models, network, media/ASR or knowledge-build.
It does not create answers or rewrite input data.

## Reproduce (stdlib only)

```sh
python3 scripts/eval/validate_qa.py --strict-kp --json
# 0: structurally/reference valid; 1: invalid data; 2: missing/unreadable input
python3 scripts/eval/validate_qa.py --strict-kp
# Human-readable file:physical-line:field diagnostics
python3 scripts/eval/validate_qa.py --path eval/retrieval/qa.jsonl --strict-kp --json > /tmp/qa-validation.json
```

Default and relative argument paths are resolved from this repository, independent
of the caller's working directory. Explicit absolute fixture/snapshot inputs can
be supplied with `--path`, `--knowledge-root`, `--index`, `--catalog`. No implicit
fallback to another checkout, untracked artifacts or ignored/deleted eval output.

The CI python job executes exactly
`python3 scripts/eval/validate_qa.py --strict-kp --json`, without piping, ignored
failure or continue-on-error, alongside all existing offline tests. Missing,
empty, comments-only or malformed input is **not success**. No input rows are
silently dropped. Blank lines and full-line `#` comments are allowed as in the
original loader; diagnostics retain the original physical line numbers.

## Actual input/baseline (not another QA dataset)

- File: **`eval/retrieval/qa.jsonl`**, already tracked in git at parent
  **`566c0ed863001bc5d53219c4a2a6936567ca2f02`** (#22).
- Exactly **50** question objects, **18,429 bytes**, SHA256
  `dc83fcc9cbf97c9ffd8d8bfb67e0480e2420dcdbad3684492d5b51515edf3097`.
- Series: shl15, jgy13, zj12, nj5, bc5. All50 have one scalar `gold_kp_id`.
- Original and revised strict validators were actually run on this same file.
  Revised result: **50 valid /0 invalid /0 errors**, **50 KP references /50 unique
  KP /37 lectures /0 video-only references**. Forty inputs are hashed: this file,
  the retained knowledge CSV, catalog and37 referenced canonical KP JSONL files.
  Two complete JSON report runs were byte-identical.
- Original questions, knowledge/index and catalog are unchanged. A regression
  pins this baseline hash/count; future intentional question changes need review
  and an explicit baseline update, not automatic regeneration to pass.

## Existing question schema, not a new multi-reference product

Required: nonblank string `id`, `question`, `series`, `gold_video_id`; JSON numeric
`gold_start_s`, `gold_end_s`, `tolerance_s`. Numbers must be finite, nonnegative,
not bool/string/null, and end ≥start. IDs are unique and stable ASCII identifiers;
lecture IDs use actual series-NNN catalog/knowledge identities, not arbitrary paths.

Optional `tags` must be a list of nonblank strings and `notes` a string. Unknown
fields, duplicate JSON keys and nonstandard NaN/Infinity tokens are rejected.

`gold_kp_id` is one string, matching the same lecture and `.kp` + digits. **CI uses
`--strict-kp` and requires it on every question.** Retaining the old optional mode
allows absent/null KP with a valid video/range, explicitly counted as video-only;
that mode is not proof of KP-source validation. It still requires readable input
snapshots. Arrays or extra multiple-reference fields are rejected, not silently
choosing the first. Two distinct questions may legitimately cite the same KP.

## Reference contract

- Lecture must exist in `web/src/data/lectures.json` and under `data/knowledge`;
  series must match its ID. Safe IDs/root containment prevent row-controlled path
  traversal or symlinks escaping the configured knowledge root.
- `data/knowledge/_index/knowledge_points.csv`: required unique header names,
  valid KP/video identities, finite ordered time fields and no duplicate KP IDs.
  Missing/empty/bad index fails; duplicates are never last-row-wins.
- Read only referenced lectures' `knowledge_points.jsonl`. Referenced canonical
  KP must exist unambiguously, with matching outer video identity and valid times.
  Malformed reference JSON lines or duplicates are reported, not filtered away.
- Question ↔ retained CSV ↔ canonical outer times must agree within **0.05s**, the
  existing numeric rounding allowance. This uses decimal comparison; question
  `tolerance_s` never relaxes the source consistency check and is not a score.
- Canonical nested `citation` must exist, have matching series/episode and finite
  ordered start/end, and agree with outer times within0.05s. Do **not** require
  the old missing `t_url` or pretend raw knowledge was migrated by this checker.
- Source `youtube_id` must match the actual catalog ID. Its URL must be matching
  HTTPS YouTube/youtu.be, no credentials/foreign ports/ambiguous video identity.
  Explicit `t`/`start` accepts the corpus's nonnegative seconds representation
  (optional `s`), not conflicting/duplicate times. The requested whole second may
  match either canonical or rounded citation start to preserve historical
  boundary rounding. No URL is fetched and no playability claim is made.

No transcript/media duration or answer-to-source entailment is verified. This
checks declared IDs/provenance/times, not whether a question is good, its cited
claim is correct, a retrieved answer finds it, ASR quality or medical truth.

## Stable machine report and failure behavior

`--json` outputs `schema: qa-validation/1`, `scope: schema_and_references`,
`strict_kp`, `ok`, `exit_code`, count/series summaries, sorted input byte hashes,
and sorted errors. It contains **`answer_quality: not_evaluated`** and
**`retrieval_metrics: null`**, never an accuracy, recall or pass-rate claim.
There are no timestamps, environment dumps, absolute checkout prefixes or file
contents in the default report. Local/CI output is deterministic for the same
input paths/bytes. Errors give `file`, physical `line`, `field`, `code`, `message`;
source association errors also give reference file/line/field when available.
Line0 means a file-level problem rather than a particular question line.

Example diagnostic shape (synthetic, not an observed dirty baseline):

```json
{"file":"eval/retrieval/qa.jsonl","line":3,"field":"gold_kp_id","code":"missing_citation","message":"Canonical KP source citation is missing.","reference_file":"data/knowledge/shl-001/knowledge_points.jsonl","reference_line":1,"reference_field":"citation"}
```

No source data is auto-fixed or rewritten. If the actual baseline ever fails,
the gate must stay failed and the issue requires review; passing tool tests are
not permission to claim the whole PR/data gate succeeded.

## Stack, verification limits and rollback

Original PR-11, base `feat/local-learning-backup@566c0ed` (#22), box-only. PR-8
remains deferred; PR-9 prerequisites remain separate; PR-12 not implemented.
The37 pre-existing eval/asr/out deletions and `.superdesign` are untouched.
No changes to knowledge, fifty questions, 24 public episodes, catalog, graph,
frontend/dependencies or production configuration. Ordinary revert removes this
validator/CI/test/doc change; no data or database migration.

Browser403/phone/real downloads/YouTube remain unverified independent premerge
checks, not bypassed or reclassified by a schema gate. PR-12 preparation only:
10 `nj` catalog rows currently label「难经」but all10 titles name「黄帝内经」;
`web/src/listen/lectures.ts` has the「难经脉络」blurb. Those inputs exist; no
rename was made or treated as external naming approval in this PR.
