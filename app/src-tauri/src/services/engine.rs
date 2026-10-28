//! Runs the forensic engine and turns its output into results and events.
//!
//! The engine prints exactly one JSON object on stdout for every command:
//! `{"success": true, ...}` on success, or
//! `{"success": false, "error": "...", "error_type": "..."}` on failure.
//! On stderr it writes diagnostics, plus progress lines of the form
//! `@@PROGRESS {"stage": ..., "done": ..., "total": ..., "message": ...}`.
//! See engine/main_cli.py for the contract.
//!
//! Where the engine comes from:
//! * installed app: the bundled `engine/suraksha-engine(.exe)` resource
//!   (built with PyInstaller, so users need no Python);
//! * development builds: `python engine/main_cli.py` from the source tree;
//! * `SURAKSHA_ENGINE` overrides both (an executable, or a folder that
//!   contains main_cli.py).

use std::collections::{HashMap, HashSet, VecDeque};
use std::env;
use std::fs::{self, OpenOptions};
use std::io::{BufRead, BufReader, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, ExitStatus, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use serde::Serialize;
use serde_json::Value;

const ENGINE_OVERRIDE_ENV: &str = "SURAKSHA_ENGINE";
const PYTHON_ENV: &str = "SURAKSHA_PYTHON";
const CASES_DIR_ENV: &str = "SURAKSHA_CASES_DIR";

const ENGINE_SCRIPT: &str = "main_cli.py";
#[cfg(windows)]
const BUNDLED_ENGINE: &str = "engine/suraksha-engine.exe";
#[cfg(not(windows))]
const BUNDLED_ENGINE: &str = "engine/suraksha-engine";

const PROGRESS_PREFIX: &str = "@@PROGRESS ";
/// Trailing stderr lines kept for error messages when the engine crashes.
const STDERR_TAIL_LINES: usize = 15;
const LOG_ROTATE_BYTES: u64 = 5 * 1024 * 1024;
const POLL_INTERVAL: Duration = Duration::from_millis(50);

/// How the engine process is started.
#[derive(Debug, Clone)]
enum Launcher {
    /// `python main_cli.py ...` (development).
    Script { python: String, script: PathBuf },
    /// The PyInstaller-built executable (installed app).
    Bundled { executable: PathBuf },
}

#[derive(Debug, Clone)]
pub struct Engine {
    launcher: Launcher,
    working_dir: PathBuf,
    cases_dir: Option<PathBuf>,
    log_file: Option<PathBuf>,
}

/// One progress report from a running job.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Progress {
    pub job_id: String,
    pub stage: String,
    pub done: Option<u64>,
    pub total: Option<u64>,
    pub message: String,
}

/// Running jobs, so the UI can cancel them.
#[derive(Default)]
pub struct JobRegistry {
    running: Mutex<HashMap<String, Arc<Mutex<Child>>>>,
    cancelled: Mutex<HashSet<String>>,
}

impl JobRegistry {
    /// Stop a running job. Returns false if no such job is running.
    pub fn cancel(&self, job_id: &str) -> bool {
        let child = self.running.lock().unwrap().get(job_id).cloned();
        match child {
            Some(child) => {
                self.cancelled.lock().unwrap().insert(job_id.to_string());
                let _ = child.lock().unwrap().kill();
                true
            }
            None => false,
        }
    }

    fn register(&self, job_id: &str, child: Arc<Mutex<Child>>) {
        self.running.lock().unwrap().insert(job_id.to_string(), child);
    }

    /// Remove a finished job; true if it had been cancelled.
    fn finish(&self, job_id: &str) -> bool {
        self.running.lock().unwrap().remove(job_id);
        self.cancelled.lock().unwrap().remove(job_id)
    }
}

impl Engine {
    /// Find the engine. `resource_dir` is the app's bundled resources.
    pub fn locate(resource_dir: Option<PathBuf>) -> Result<Self, String> {
        if let Ok(path) = env::var(ENGINE_OVERRIDE_ENV) {
            let path = PathBuf::from(path);
            return Self::from_path(&path).ok_or_else(|| {
                format!(
                    "{ENGINE_OVERRIDE_ENV} is set to {}, which is neither the engine \
                     executable nor a folder containing {ENGINE_SCRIPT}.",
                    path.display()
                )
            });
        }

        // Development builds run the Python source next to the app.
        if cfg!(debug_assertions) {
            let source = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../engine");
            if let Some(engine) = Self::from_path(&source) {
                return Ok(engine);
            }
        }

        if let Some(engine) = resource_dir
            .map(|dir| dir.join(BUNDLED_ENGINE))
            .and_then(|path| Self::from_path(&path))
        {
            return Ok(engine);
        }

        Err(format!(
            "The forensic engine was not found. Reinstall the application, or set \
             {ENGINE_OVERRIDE_ENV} to the engine executable."
        ))
    }

    fn from_path(path: &Path) -> Option<Self> {
        if path.is_file() {
            let working_dir = path.parent()?.to_path_buf();
            return Some(Self {
                launcher: Launcher::Bundled { executable: path.to_path_buf() },
                working_dir,
                cases_dir: None,
                log_file: None,
            });
        }
        let script = path.join(ENGINE_SCRIPT);
        script.is_file().then(|| Self {
            launcher: Launcher::Script {
                python: env::var(PYTHON_ENV).unwrap_or_else(|_| "python".to_string()),
                script,
            },
            working_dir: path.to_path_buf(),
            cases_dir: None,
            log_file: None,
        })
    }

    /// Keep case databases and logs in the user's application data.
    pub fn with_data_dirs(mut self, cases_dir: Option<PathBuf>, log_dir: Option<PathBuf>) -> Self {
        if env::var(CASES_DIR_ENV).is_err() {
            self.cases_dir = cases_dir;
        }
        self.log_file = log_dir.map(|dir| dir.join("engine.log"));
        self
    }

    pub fn description(&self) -> String {
        match &self.launcher {
            Launcher::Script { python, script } => format!("{python} {}", script.display()),
            Launcher::Bundled { executable } => executable.display().to_string(),
        }
    }

    pub fn log_file(&self) -> Option<&Path> {
        self.log_file.as_deref()
    }

    fn command(&self, command: &str, args: &[String]) -> Command {
        let mut process = match &self.launcher {
            Launcher::Script { python, script } => {
                let mut process = Command::new(python);
                process.arg(script);
                process
            }
            Launcher::Bundled { executable } => Command::new(executable),
        };
        process
            .arg(command)
            .args(args)
            .current_dir(&self.working_dir)
            // Non-ASCII file names must not crash the engine's output.
            .env("PYTHONIOENCODING", "utf-8")
            .env("PYTHONUTF8", "1")
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        if let Some(dir) = &self.cases_dir {
            process.env(CASES_DIR_ENV, dir);
        }

        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            process.creation_flags(CREATE_NO_WINDOW);
        }
        process
    }

    /// Run one engine command on a background thread.
    ///
    /// With a `job`, progress lines are passed to `on_progress` and the job
    /// can be cancelled through the registry.
    pub async fn run<F>(
        &self,
        command: &str,
        args: Vec<String>,
        job: Option<(Arc<JobRegistry>, String)>,
        on_progress: F,
    ) -> Result<Value, String>
    where
        F: Fn(Progress) + Send + 'static,
    {
        let mut process = self.command(command, &args);
        let log_file = self.log_file.clone();
        let command_name = command.to_string();
        let description = self.description();

        tauri::async_runtime::spawn_blocking(move || {
            let mut child = process.spawn().map_err(|error| {
                format!("Failed to start the forensic engine ({description}): {error}")
            })?;
            let stdout = child.stdout.take();
            let stderr = child.stderr.take();

            let stdout_reader = thread::spawn(move || {
                let mut buffer = Vec::new();
                if let Some(mut stdout) = stdout {
                    let _ = stdout.read_to_end(&mut buffer);
                }
                buffer
            });

            let job_id = job.as_ref().map(|(_, id)| id.clone()).unwrap_or_default();
            let log_header = format!("[{}] {command_name} {}", unix_time(), args.join(" "));
            let stderr_reader = thread::spawn(move || {
                read_stderr(stderr, &job_id, &on_progress, log_file.as_deref(), &log_header)
            });

            let child = Arc::new(Mutex::new(child));
            if let Some((registry, id)) = &job {
                registry.register(id, child.clone());
            }
            let status = loop {
                match child.lock().unwrap().try_wait() {
                    Ok(Some(status)) => break Ok(status),
                    Ok(None) => {}
                    Err(error) => break Err(error),
                }
                thread::sleep(POLL_INTERVAL);
            };
            let cancelled = job
                .as_ref()
                .map(|(registry, id)| registry.finish(id))
                .unwrap_or(false);

            let stdout = stdout_reader.join().unwrap_or_default();
            let stderr_tail = stderr_reader.join().unwrap_or_default();
            let status = status.map_err(|error| format!("Lost track of the forensic engine: {error}"))?;

            if cancelled {
                return Err("Cancelled.".to_string());
            }
            interpret(&command_name, status, &stdout, &stderr_tail)
        })
        .await
        .map_err(|error| format!("The forensic engine task failed: {error}"))?
    }
}

/// Route stderr: progress lines to the callback, the rest to the log.
/// Returns the last lines, for error messages.
fn read_stderr<F: Fn(Progress)>(
    stderr: Option<impl Read>,
    job_id: &str,
    on_progress: &F,
    log_file: Option<&Path>,
    log_header: &str,
) -> String {
    let mut log = log_file.and_then(open_log);
    if let Some(log) = log.as_mut() {
        let _ = writeln!(log, "{log_header}");
    }
    let mut tail: VecDeque<String> = VecDeque::with_capacity(STDERR_TAIL_LINES);
    let Some(stderr) = stderr else { return String::new() };

    for line in BufReader::new(stderr).lines().map_while(Result::ok) {
        if let Some(payload) = line.strip_prefix(PROGRESS_PREFIX) {
            if let Ok(value) = serde_json::from_str::<Value>(payload) {
                on_progress(Progress {
                    job_id: job_id.to_string(),
                    stage: value["stage"].as_str().unwrap_or_default().to_string(),
                    done: value["done"].as_u64(),
                    total: value["total"].as_u64(),
                    message: value["message"].as_str().unwrap_or_default().to_string(),
                });
            }
            continue;
        }
        if let Some(log) = log.as_mut() {
            let _ = writeln!(log, "  {line}");
        }
        if !line.trim().is_empty() {
            if tail.len() == STDERR_TAIL_LINES {
                tail.pop_front();
            }
            tail.push_back(line);
        }
    }
    tail.into_iter().collect::<Vec<_>>().join("\n")
}

fn open_log(path: &Path) -> Option<fs::File> {
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    if fs::metadata(path).map(|m| m.len() > LOG_ROTATE_BYTES).unwrap_or(false) {
        let _ = fs::rename(path, path.with_extension("log.1"));
    }
    OpenOptions::new().create(true).append(true).open(path).ok()
}

fn unix_time() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/// Turn the engine's exit status and output into a result.
fn interpret(command: &str, status: ExitStatus, stdout: &[u8], stderr_tail: &str) -> Result<Value, String> {
    let stdout = String::from_utf8_lossy(stdout);

    // The result is the last non-empty stdout line.
    let parsed = stdout
        .lines()
        .rev()
        .find(|line| !line.trim().is_empty())
        .and_then(|line| serde_json::from_str::<Value>(line).ok())
        .filter(Value::is_object);

    match parsed {
        Some(result) if result.get("success") == Some(&Value::Bool(true)) => {
            if status.success() {
                Ok(result)
            } else {
                Err(format!(
                    "The forensic engine reported success for '{command}' but exited with {status}."
                ))
            }
        }
        Some(result) => Err(result
            .get("error")
            .and_then(Value::as_str)
            .filter(|message| !message.trim().is_empty())
            .map(str::to_string)
            .unwrap_or_else(|| format!("The forensic engine could not run '{command}'."))),
        None if stderr_tail.is_empty() => Err(format!(
            "The forensic engine stopped without a result while running '{command}' ({status})."
        )),
        None => Err(format!(
            "The forensic engine stopped without a result while running '{command}' ({status}):\n{stderr_tail}"
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[cfg(windows)]
    use std::os::windows::process::ExitStatusExt;
    #[cfg(unix)]
    use std::os::unix::process::ExitStatusExt;

    fn status(code: u32) -> ExitStatus {
        #[cfg(windows)]
        return ExitStatus::from_raw(code);
        #[cfg(unix)]
        return ExitStatus::from_raw((code as i32) << 8);
    }

    fn dev_engine() -> Option<Engine> {
        if env::var(ENGINE_OVERRIDE_ENV).is_ok() {
            return None;
        }
        Engine::locate(None).ok()
    }

    #[test]
    fn success_returns_the_json_object() {
        let result = interpret("evidence", status(0), b"{\"success\": true, \"count\": 2}\n", "");
        assert_eq!(result.unwrap()["count"], 2);
    }

    #[test]
    fn failure_returns_the_engine_error_message() {
        let stdout = b"{\"success\": false, \"error\": \"Case database not found: x.db\"}\n";
        let error = interpret("evidence", status(1), stdout, "Traceback ...").unwrap_err();
        assert_eq!(error, "Case database not found: x.db");
    }

    #[test]
    fn crash_without_json_includes_the_end_of_stderr() {
        let error = interpret("analyze", status(1), b"", "Traceback\nKeyError: 'x'").unwrap_err();
        assert!(error.contains("KeyError: 'x'"), "{error}");
    }

    #[test]
    fn stray_lines_before_the_result_are_ignored() {
        assert!(interpret("timeline", status(0), b"noise\n{\"success\": true}\n", "").is_ok());
    }

    #[test]
    fn progress_lines_are_routed_and_others_kept() {
        let stderr = "Reading boot sector\n@@PROGRESS {\"stage\": \"Reading MFT records\", \"done\": 5, \"total\": 10, \"message\": \"\"}\nbye\n";
        let seen = Mutex::new(Vec::new());
        let tail = read_stderr(Some(stderr.as_bytes()), "job-1", &|p: Progress| seen.lock().unwrap().push(p), None, "");
        let seen = seen.into_inner().unwrap();
        assert_eq!(seen.len(), 1);
        assert_eq!(seen[0].job_id, "job-1");
        assert_eq!((seen[0].done, seen[0].total), (Some(5), Some(10)));
        assert_eq!(tail, "Reading boot sector\nbye");
    }

    #[test]
    fn locates_the_engine_source_in_development() {
        if let Some(engine) = dev_engine() {
            assert!(engine.description().contains(ENGINE_SCRIPT));
        }
    }

    #[test]
    fn real_engine_errors_arrive_as_readable_messages() {
        let Some(engine) = dev_engine() else { return };
        let result = tauri::async_runtime::block_on(engine.run(
            "evidence",
            vec!["missing-case.db".into(), "1".into()],
            None,
            |_| {},
        ));
        let error = result.expect_err("a missing database must be an error");
        if error.starts_with("Failed to start") {
            return; // no Python on this machine
        }
        assert!(error.contains("Case database not found"), "{error}");
    }

    #[test]
    fn running_jobs_can_be_cancelled() {
        let Some(engine) = dev_engine() else { return };
        let registry = Arc::new(JobRegistry::default());
        let canceller = registry.clone();
        thread::spawn(move || {
            // Cancel as soon as the job is registered.
            for _ in 0..200 {
                if canceller.cancel("slow") {
                    return;
                }
                thread::sleep(Duration::from_millis(10));
            }
        });
        let result = tauri::async_runtime::block_on(engine.run(
            "version",
            vec![],
            Some((registry, "slow".into())),
            |_| {},
        ));
        // Either it was cancelled first, or `version` finished first.
        match result {
            Err(error) => assert_eq!(error, "Cancelled."),
            Ok(value) => assert_eq!(value["success"], true),
        }
    }
}
