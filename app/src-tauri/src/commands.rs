//! Tauri commands exposed to the frontend.
//!
//! Each command maps one-to-one onto a forensic engine command and returns
//! the engine's JSON result as an object. Argument validation lives in the
//! engine (main_cli.py), so it is defined once.
//!
//! All commands are async: the engine runs on a background thread, so the
//! window never freezes. Long commands take an optional `job_id`; while
//! they run, progress arrives as `engine-progress` events tagged with that
//! id, and `cancel_job(job_id)` stops them.

use std::sync::Arc;

use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, State};

use crate::services::engine::{Engine, JobRegistry};

pub const PROGRESS_EVENT: &str = "engine-progress";

/// The engine located at startup (or why it could not be found) and the
/// jobs currently running.
pub struct EngineState {
    pub engine: Result<Engine, String>,
    pub jobs: Arc<JobRegistry>,
}

type CommandResult = Result<Value, String>;

async fn run(
    state: &State<'_, EngineState>,
    app: &AppHandle,
    command: &str,
    args: Vec<String>,
    job_id: Option<String>,
) -> CommandResult {
    let engine = state.engine.as_ref().map_err(Clone::clone)?;
    let job = job_id.map(|id| (state.jobs.clone(), id));
    let app = app.clone();
    engine
        .run(command, args, job, move |progress| {
            let _ = app.emit(PROGRESS_EVENT, progress);
        })
        .await
}

fn flag(args: &mut Vec<String>, name: &str, value: Option<String>) {
    if let Some(value) = value.filter(|value| !value.trim().is_empty()) {
        args.push(name.to_string());
        args.push(value);
    }
}

fn join_ids(ids: &[i64]) -> String {
    ids.iter().map(i64::to_string).collect::<Vec<_>>().join(",")
}

// ----------------------------------------------------------------------
// Application and cases
// ----------------------------------------------------------------------

/// Where the engine runs from and where data is kept (for the About box
/// and support).
#[tauri::command]
pub async fn engine_info(state: State<'_, EngineState>, app: AppHandle) -> CommandResult {
    let engine = state.engine.as_ref().map_err(Clone::clone)?;
    let mut info = run(&state, &app, "version", vec![], None).await?;
    info["engine"] = json!(engine.description());
    info["log_file"] = json!(engine.log_file().map(|p| p.display().to_string()));
    info["app_version"] = json!(app.package_info().version.to_string());
    Ok(info)
}

#[tauri::command]
pub async fn list_cases(state: State<'_, EngineState>, app: AppHandle) -> CommandResult {
    run(&state, &app, "list-cases", vec![], None).await
}

#[tauri::command]
pub fn cancel_job(state: State<'_, EngineState>, job_id: String) -> bool {
    state.jobs.cancel(&job_id)
}

#[tauri::command]
pub async fn start_analysis(
    state: State<'_, EngineState>,
    app: AppHandle,
    image_path: String,
    case_name: Option<String>,
    investigator: Option<String>,
    description: Option<String>,
    job_id: Option<String>,
) -> CommandResult {
    let mut args = vec![image_path];
    flag(&mut args, "--case-name", case_name);
    flag(&mut args, "--investigator", investigator);
    flag(&mut args, "--description", description);
    run(&state, &app, "analyze", args, job_id).await
}

// ----------------------------------------------------------------------
// Browsing a case
// ----------------------------------------------------------------------

#[tauri::command]
pub async fn get_evidence(
    state: State<'_, EngineState>,
    app: AppHandle,
    database_path: String,
    case_id: i64,
) -> CommandResult {
    run(&state, &app, "evidence", vec![database_path, case_id.to_string()], None).await
}

#[tauri::command]
pub async fn get_filesystem_tree(
    state: State<'_, EngineState>,
    app: AppHandle,
    database_path: String,
    case_id: i64,
) -> CommandResult {
    run(&state, &app, "filesystem", vec![database_path, case_id.to_string()], None).await
}

#[tauri::command]
pub async fn get_preview(
    state: State<'_, EngineState>,
    app: AppHandle,
    database_path: String,
    evidence_id: i64,
    artifact_path: Option<String>,
) -> CommandResult {
    let mut args = vec![database_path, evidence_id.to_string()];
    args.extend(artifact_path);
    run(&state, &app, "preview", args, None).await
}

#[tauri::command]
pub async fn get_timeline_graph(
    state: State<'_, EngineState>,
    app: AppHandle,
    database_path: String,
    case_id: i64,
    interval: String,
    record_number: Option<i64>,
) -> CommandResult {
    let mut args = vec![database_path, case_id.to_string(), interval];
    args.extend(record_number.map(|record| record.to_string()));
    run(&state, &app, "timeline", args, None).await
}

#[tauri::command]
pub async fn get_file_slack(
    state: State<'_, EngineState>,
    app: AppHandle,
    database_path: String,
    evidence_id: i64,
) -> CommandResult {
    run(&state, &app, "file-slack", vec![database_path, evidence_id.to_string()], None).await
}

#[tauri::command]
pub async fn get_metafiles(
    state: State<'_, EngineState>,
    app: AppHandle,
    database_path: String,
    case_id: i64,
) -> CommandResult {
    run(&state, &app, "metafiles", vec![database_path, case_id.to_string()], None).await
}

#[tauri::command]
pub async fn extract_metafiles(
    state: State<'_, EngineState>,
    app: AppHandle,
    image_path: String,
    database_path: String,
    case_id: i64,
    destination: String,
    job_id: Option<String>,
) -> CommandResult {
    let args = vec![image_path, database_path, case_id.to_string(), destination];
    run(&state, &app, "extract-metafiles", args, job_id).await
}

// ----------------------------------------------------------------------
// Free space
// ----------------------------------------------------------------------

#[tauri::command]
pub async fn get_unallocated_regions(
    state: State<'_, EngineState>,
    app: AppHandle,
    image_path: String,
    database_path: String,
    case_id: i64,
) -> CommandResult {
    let args = vec![image_path, database_path, case_id.to_string()];
    run(&state, &app, "unallocated-regions", args, None).await
}

#[tauri::command]
pub async fn read_unallocated_region(
    state: State<'_, EngineState>,
    app: AppHandle,
    image_path: String,
    database_path: String,
    case_id: i64,
    region_index: i64,
    offset: i64,
    size: i64,
) -> CommandResult {
    let args = vec![
        image_path,
        database_path,
        case_id.to_string(),
        region_index.to_string(),
        offset.to_string(),
        size.to_string(),
    ];
    run(&state, &app, "read-unallocated", args, None).await
}

#[tauri::command]
pub async fn recover_unallocated(
    state: State<'_, EngineState>,
    app: AppHandle,
    image_path: String,
    database_path: String,
    case_id: i64,
    job_id: Option<String>,
) -> CommandResult {
    let args = vec![image_path, database_path, case_id.to_string()];
    run(&state, &app, "recover-unallocated", args, job_id).await
}

#[tauri::command]
pub async fn get_recovered_artifacts(
    state: State<'_, EngineState>,
    app: AppHandle,
    database_path: String,
    case_id: i64,
) -> CommandResult {
    run(&state, &app, "recovered-artifacts", vec![database_path, case_id.to_string()], None).await
}

#[tauri::command]
pub async fn preview_recovered(
    state: State<'_, EngineState>,
    app: AppHandle,
    image_path: String,
    database_path: String,
    case_id: i64,
    artifact_id: i64,
) -> CommandResult {
    let args = vec![image_path, database_path, case_id.to_string(), artifact_id.to_string()];
    run(&state, &app, "recovered-preview", args, None).await
}

#[tauri::command]
pub async fn export_recovered(
    state: State<'_, EngineState>,
    app: AppHandle,
    image_path: String,
    database_path: String,
    case_id: i64,
    destination: String,
    artifact_ids: Option<Vec<i64>>,
    job_id: Option<String>,
) -> CommandResult {
    let mut args = vec![image_path, database_path, case_id.to_string(), destination];
    flag(&mut args, "--ids", artifact_ids.map(|ids| join_ids(&ids)));
    run(&state, &app, "export-recovered", args, job_id).await
}

// ----------------------------------------------------------------------
// Deleted files
// ----------------------------------------------------------------------

#[tauri::command]
pub async fn get_deleted_files(
    state: State<'_, EngineState>,
    app: AppHandle,
    database_path: String,
    case_id: i64,
) -> CommandResult {
    run(&state, &app, "deleted-files", vec![database_path, case_id.to_string()], None).await
}

/// Restore deleted files. `statuses` defaults to recoverable + partial;
/// `record_numbers` limits the restore to chosen files.
#[tauri::command]
#[allow(clippy::too_many_arguments)]
pub async fn recover_deleted(
    state: State<'_, EngineState>,
    app: AppHandle,
    image_path: String,
    database_path: String,
    case_id: i64,
    destination: String,
    statuses: Option<Vec<String>>,
    record_numbers: Option<Vec<i64>>,
    job_id: Option<String>,
) -> CommandResult {
    let mut args = vec![image_path, database_path, case_id.to_string(), destination];
    flag(&mut args, "--status", statuses.map(|list| list.join(",")));
    flag(&mut args, "--records", record_numbers.map(|ids| join_ids(&ids)));
    run(&state, &app, "recover-deleted", args, job_id).await
}
