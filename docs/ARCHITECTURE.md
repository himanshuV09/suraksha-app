# Architecture

```
┌──────────────────────────┐   invoke()    ┌──────────────────────────┐   process   ┌──────────────────────────┐
│ React UI (app/src)       │ ───────────▶ │ Rust shell (src-tauri)   │ ──────────▶ │ Forensic engine (Python) │
│ screens, previews,       │ ◀─────────── │ commands.rs, engine.rs   │ ◀────────── │ main_cli.py <command>    │
│ progress bars            │ result/event │ job registry, logging    │ JSON/stderr │ reads image, writes .db  │
└──────────────────────────┘              └──────────────────────────┘             └────────────┬─────────────┘
                                                                                               │
                                                                               SQLite case database (per case name)
```

* **UI** calls Tauri commands through `src/lib/engine.ts` (`callEngine`,
  `runJob`). Long jobs get a job id; progress arrives as
  `engine-progress` events and `cancel_job(id)` stops the job.
* **Rust** (`src-tauri/src/services/engine.rs`) starts the engine for each
  command, on a background thread so the window never blocks. It sets
  `SURAKSHA_CASES_DIR` to the user's app-data folder, routes stderr
  progress lines to events and everything else to `engine.log`, and turns
  the engine's JSON into the command result.
* **Engine** (`engine/main_cli.py`) parses the image and stores results in
  the case database. Commands that only read results (evidence, timeline,
  regions, hex pages) never re-parse the image.

## Engine output contract

Every command, without exception:

* prints **exactly one JSON object** on stdout;
* success: `{"success": true, ...}`, exit code 0;
* failure: `{"success": false, "error": "...", "error_type": "...", "command": "..."}`,
  exit code 1, or 2 for invalid usage;
* writes diagnostics, tracebacks and progress to stderr only. Progress lines are
  `@@PROGRESS {"stage", "done", "total", "message"}`, throttled to 4/s.

## Engine commands

| Command | Purpose |
|---|---|
| `analyze image_path [--case-name] [--investigator] [--description] [--cases-dir]` | Full analysis; creates a case |
| `list-cases [--cases-dir]` | Cases in the cases folder (read-only) |
| `version` | Engine version, Python version, frozen or not |
| `evidence db case_id` | All MFT records of a case |
| `filesystem db case_id` | Directory tree (with container members and free space) |
| `preview db evidence_id [artifact_path]` | Preview a file, or a member of a ZIP/Office file |
| `timeline db case_id [day\|week\|month\|year] [record_number]` | Timeline graph and events |
| `file-slack db evidence_id` | Slack bytes and readable strings of a file |
| `metafiles db case_id` | NTFS metafile summary |
| `extract-metafiles image db case_id folder` | Raw metafile streams (sparse-aware) |
| `deleted-files db case_id [--status]` | Deleted files with recoverability grades |
| `recover-deleted image db case_id folder [--status] [--records]` | Restore deleted files with a manifest |
| `unallocated-regions image db case_id` | Free-space regions |
| `read-unallocated image db case_id region offset size` | Raw bytes of a free region (≤ 64 KiB) |
| `recover-unallocated image db case_id` | Carve files from free space |
| `recovered-artifacts db case_id` | Carved files |
| `recovered-preview image db case_id artifact_id` | Preview a carved file (hash re-checked) |
| `export-recovered image db case_id folder [--ids]` | Export carved files with a manifest |

## Case database

One SQLite file per case name (`<case name>.db`). Tables:

| Table | Contents |
|---|---|
| `cases` | name, image, investigator, description, status (`running` / `complete` / `failed`), engine version |
| `evidence` | one row per MFT record |
| `container_artifacts` | members of ZIP/Office files |
| `timeline_events` | MFT, USN, LOGFILE, I30 and MFT_SLACK events |
| `metafiles` | per-metafile summary (JSON details) |
| `deleted_files` | recoverability grade, unreliable byte ranges, content check |
| `unallocated_regions` | free-space regions from `$Bitmap` |
| `recovered_artifacts` | carved files: location, SHA-256, fragments, validation reason |

Columns added after the first release are appended and migrated
automatically when an older database is opened.

## Error handling

* A malformed MFT record is skipped, counted and reported, never fatal.
* Each metafile analyzer is isolated: a damaged metafile becomes a
  warning in the analysis result.
* An interrupted analysis leaves its case marked `running`, shown as
  *Interrupted* on the Cases screen.
* UI screens are wrapped in an error boundary, so one failing screen does
  not blank the window.
