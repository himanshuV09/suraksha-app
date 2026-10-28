mod commands;
mod services;

use std::sync::Arc;

use tauri::Manager;

use commands::EngineState;
use services::engine::{Engine, JobRegistry};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            // Locate the engine once. If it is missing, every command
            // reports the same clear message instead of the app failing.
            let paths = app.path();
            let engine = Engine::locate(paths.resource_dir().ok()).map(|engine| {
                engine.with_data_dirs(
                    paths.app_data_dir().ok().map(|dir| dir.join("cases")),
                    paths.app_log_dir().ok(),
                )
            });
            match &engine {
                Ok(engine) => eprintln!("Forensic engine: {}", engine.description()),
                Err(error) => eprintln!("Forensic engine not available: {error}"),
            }
            app.manage(EngineState {
                engine,
                jobs: Arc::new(JobRegistry::default()),
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::engine_info,
            commands::list_cases,
            commands::cancel_job,
            commands::start_analysis,
            commands::get_evidence,
            commands::get_filesystem_tree,
            commands::get_preview,
            commands::get_timeline_graph,
            commands::get_file_slack,
            commands::get_metafiles,
            commands::extract_metafiles,
            commands::get_unallocated_regions,
            commands::read_unallocated_region,
            commands::recover_unallocated,
            commands::get_recovered_artifacts,
            commands::preview_recovered,
            commands::export_recovered,
            commands::get_deleted_files,
            commands::recover_deleted,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
