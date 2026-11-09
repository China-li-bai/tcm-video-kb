# Local learning backup (PR-10, not cloud sync)

Entry: **收获匣 → 备份与导入学习记录** (`/stash`, below saved quotes).
Information hierarchy stays saved quotes first; backup/download, then local file
selection and preview, then a separate explicit confirmation. Existing CSS and
fixed-height watch/player/transcript shell are unchanged. No new settings page.

## File contract: `listen-state/1`

```json
{
  "schema": "listen-state/1",
  "renji.listen.stash.v1": [
    {"id":"example", "videoId":"shl-001", "title":"", "text":"合成示例", "t":0, "savedAt":"2026-11-09"}
  ],
  "renji.listen.lastWatch.v1": null
}
```

Only these two application keys are exported. No storage enumeration, cookies,
credentials, general browser history, current URL or recovery journal is exported.
The file is **not encrypted**; it includes your saved quotes and request location.
No file or learning state is uploaded; there are no network calls, accounts,
analytics or cloud synchronization in this feature. Existing optional recall
reveal/toast state is transient, not a separate persistent score/history.

- UTF-8 file limit: **2 MiB**, checked before reading the selected File and again
  after decoding and when serializing the merged result. At most **200** quotes.
- Exact root/record allowlists: unknown fields (including arbitrary URL and
  prototype-pollution keys) and unsupported/unversioned/future schemas fail closed.
  Quoted URL/HTML-looking **text** remains inert text, not an executable link.
- Quote fields: `id`, `videoId`, `title`, `text`, `savedAt`, optional `t`.
  `id`: 1–128 ASCII letters/digits/underscore/hyphen; `videoId`: actual catalog ID.
  Title ≤1000 UTF-16 units (empty permitted), nonblank quote ≤10000 units.
- Last request: `videoId`, `title`, `updatedAt`, optional `t`, `chapterId`,
  `chapterTitle`. Chapter IDs must have the same lecture prefix and `.c` + digits.
  Chapter titles ≤1000 units. Links are derived from the catalog, not file URLs.
- Seconds must be finite, nonnegative and ≤Number.MAX_SAFE_INTEGER. Missing `t`
  stays missing; zero/fractional historical data roundtrips. The existing link
  contract floors request seconds on navigation. This is **not playback telemetry,
  completion or proof of listening**. Legacy v1 optional fields/date-only stamps
  are supported; this is the first file format, not an import of arbitrary storage.
- Dates: real calendar `YYYY-MM-DD` or ISO timestamp with seconds and explicit
  `Z`/offset, optional 1–3 fractional digits, ≤64 units. Invalid day/24:00 rollover
  is rejected rather than silently normalized. Offsets are preserved in the file.
- Damaged/unreadable local keys block export/import, rather than exporting an
  empty fallback or replacing bad data. Existing display readers tolerate bad
  top-level shapes without rewriting them; valid records remain available.

## Preview and merge

FileReader reads only the explicitly selected file; stale read results and route
leave are canceled/ignored. Preview does not write. It shows planned added,
conflicting and capacity-skipped counts, request identity/seconds, and the first
five new quotes (160 Unicode codepoints each; stored/imported text stays whole).
Cancel, a new selection, bad file or read failure removes the previous confirmation.

On **确认合并导入**:

1. Existing quote values and order always win. Deduplicate by `videoId + text`;
   colliding `id` also keeps the existing record. Within the incoming file, the
   first accepted record wins. New records append in file order.
2. Fill only remaining slots up to 200, report skipped records, never truncate
   existing data. An empty file state cannot clear existing records.
3. Existing `lastWatch` wins regardless of timestamps. Fill it only if absent/null.
   Preserve its request-position meaning. No fake following/progress is introduced.
4. Verify the raw two-key snapshot still matches the preview. If changed, refuse
   and require re-preview; no silent rebase under the confirmation.

## Storage failure and recovery: bounded, not atomic

Before changing either data key, persist an internal
`renji.listen.importRecovery.v1` journal containing only the exact two-key raw
before/after snapshots. If journal creation fails (quota/permission), no data key
is changed. Unchanged data keys are not rewritten; a no-op writes nothing.

On a later failure, attempt exact rollback (including whitespace and absent keys).
Do not overwrite a written key if it has since changed away from the expected
import value. If rollback/cleanup cannot complete, retain the durable original
journal. On reopening `/stash`, new imports are blocked and the user can:

- **下载导入前原记录**: download the original canonical `listen-state/1` state;
- **重试恢复原记录**: restore exact original raw keys, refusing subsequent edits;
- **保留当前记录并清理恢复备份**: explicitly accept current readable state and
  discard only the recovery journal, not the learning keys.

Multi-key localStorage is **not a transaction**. Other readers can observe an
intermediate state; there is no cross-tab lock/CAS guarantee. Stop other tabs'
save/position operations and download a backup first. Browser deletion, eviction,
private-mode restrictions, disk/device failure or concurrent writers can prevent
recovery; an unreadable/damaged journal is retained and reported, not trusted or
automatically removed. The recovery copy is in the same browser, not off-device.
Normal legacy save/toast behavior outside this backup workflow is not redesigned.

Download uses a local Blob URL and cleans it up on the next task or unmount. The
UI says download was **initiated**; only the user/browser can confirm disk output.
No actual private user file was imported during development; all new fixtures
are synthetic. jsdom covers events/effects, not download permissions, real file
pickers, mobile geometry or real browser persistence. The existing browser403,
PC/phone layout and YouTube premerge acceptance gates remain unverified.

## Stack / rollback

Original **PR-10**, stacked directly on PR-7 #21 (`dc83928`): PR-8 is deferred
under its original measured trigger; PR-9 has no code and its MFK/privacy research
remains blocked separately. This PR adds no MFK/legal scope and starts no PR-11.
No original knowledge, 24-episode assets, manifest, graph snapshot, dependencies
or production configuration changes. No deployment or main merge.

Ordinary revert removes the feature; it does not reset existing learning keys.
If a recovery journal is pending, download/recover it with this version before
reverting: older builds do not interpret the new internal recovery key. Imported
records use the existing v1 learning keys and remain readable by prior versions.
