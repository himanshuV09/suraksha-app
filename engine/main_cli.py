"""Command-line entry point for the forensic engine.

The Suraksha desktop app runs ``python main_cli.py <command> [args...]``.

Output contract, identical for every command:

* stdout carries exactly one JSON object and nothing else.
* Success: ``{"success": true, ...}`` and exit code 0.
* Failure: ``{"success": false, "error": "<message>",
  "error_type": "<kind>", "command": "<command>"}`` and exit code 1
  (exit code 2 when the command line itself is invalid).
* Progress messages, diagnostics and tracebacks go to stderr only.

Commands:

    analyze <image_path> [--case-name N] [--investigator N] [--description T]
            [--cases-dir D]
    list-cases [--cases-dir D]
    version
    evidence <database_path> <case_id>
    filesystem <database_path> <case_id>
    preview <database_path> <evidence_id> [artifact_path]
    timeline <database_path> <case_id> [day|week|month|year] [record_number]
    unallocated-regions <image_path> <database_path> <case_id>
    read-unallocated <image_path> <database_path> <case_id>
                     <region_index> <offset> <size>
    recover-unallocated <image_path> <database_path> <case_id>
    recovered-artifacts <database_path> <case_id>
    recovered-preview <image_path> <database_path> <case_id> <artifact_id>
    export-recovered <image_path> <database_path> <case_id> <destination> [--ids 1,2]
    file-slack <database_path> <evidence_id>
    deleted-files <database_path> <case_id> [--status recoverable,partial,...]
    recover-deleted <image_path> <database_path> <case_id> <destination>
                    [--status recoverable,partial] [--records 41,42]
    metafiles <database_path> <case_id>
    extract-metafiles <image_path> <database_path> <case_id> <destination>
"""
import argparse
import importlib
import json
import sys
import traceback
from contextlib import redirect_stdout

from engine.defaults import DEFAULT_CASE_NAME, DEFAULT_INVESTIGATOR
from engine.errors import UsageError

# Each command imports only what it needs: the desktop app starts a new
# process per action (e.g. every hex-view page), and importing every API
# (python-docx, python-pptx, the whole pipeline) cost ~200 ms per call.
_API_MODULES = {
    "ForensicEngine": "engine.engine",
    "EvidenceAPI": "engine.api.evidence_api",
    "FilesystemAPI": "engine.api.filesystem_api",
    "MetafileAPI": "engine.api.metafile_api",
    "DeletedFileAPI": "engine.api.deleted_file_api",
    "CaseAPI": "engine.api.case_api",
    "SlackAPI": "engine.api.slack_api",
    "PreviewAPI": "engine.api.preview_api",
    "RecoveredArtifactAPI": "engine.api.recovered_artifact_api",
    "TimelineAPI": "engine.api.timeline_api",
    "UnallocatedAPI": "engine.api.unallocated_api",
}


def _api(name):
    """The class ``name``, imported on first use.

    A module-level attribute of the same name takes precedence, so tests
    can substitute an API with monkeypatch.setattr(main_cli, name, ...).
    """
    override = globals().get(name)
    if override is not None:
        return override
    return getattr(importlib.import_module(_API_MODULES[name]), name)

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2

TIMELINE_INTERVALS = ("day", "week", "month", "year")


# ---------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------

class _ArgumentParser(argparse.ArgumentParser):
    """An ArgumentParser that raises UsageError instead of exiting."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("add_help", False)
        super().__init__(*args, **kwargs)

    def error(self, message):
        usage = " ".join(self.format_usage().split())
        if usage.lower().startswith("usage:"):
            usage = usage[len("usage:"):].strip()
        raise UsageError(f"Usage: {usage} ({message})")


def _int_at_least(minimum, label):
    def convert(value):
        try:
            number = int(value)
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"{label} must be an integer, got {value!r}"
            )
        if number < minimum:
            raise argparse.ArgumentTypeError(
                f"{label} must be at least {minimum}, got {number}"
            )
        return number

    return convert


def _comma_list(convert, label):
    def parse(value):
        items = [item.strip() for item in value.split(",") if item.strip()]
        if not items:
            raise argparse.ArgumentTypeError(f"{label} cannot be empty")
        return [convert(item) for item in items]
    return parse


_status_list = _comma_list(str.lower, "status")
_record_list = _comma_list(_int_at_least(0, "record number"), "records")
_case_id = _int_at_least(1, "case_id")
_evidence_id = _int_at_least(1, "evidence_id")
_record_number = _int_at_least(0, "record_number")
_region_index = _int_at_least(0, "region_index")
_offset = _int_at_least(0, "offset")
_size = _int_at_least(1, "size")


def build_parser():
    parser = _ArgumentParser(prog="main_cli.py")
    commands = parser.add_subparsers(
        dest="command",
        metavar="<command>",
        parser_class=_ArgumentParser,
    )

    analyze = commands.add_parser("analyze")
    analyze.add_argument("image_path")
    analyze.add_argument("--case-name", default=DEFAULT_CASE_NAME)
    analyze.add_argument("--investigator", default=DEFAULT_INVESTIGATOR)
    analyze.add_argument("--cases-dir", default=None)
    analyze.add_argument("--description", default="")
    analyze.set_defaults(handler=_analyze)

    cases = commands.add_parser("list-cases")
    cases.add_argument("--cases-dir", default=None)
    cases.set_defaults(handler=_list_cases)

    version = commands.add_parser("version")
    version.set_defaults(handler=_version)

    evidence = commands.add_parser("evidence")
    evidence.add_argument("database_path")
    evidence.add_argument("case_id", type=_case_id)
    evidence.set_defaults(handler=_evidence)

    filesystem = commands.add_parser("filesystem")
    filesystem.add_argument("database_path")
    filesystem.add_argument("case_id", type=_case_id)
    filesystem.set_defaults(handler=_filesystem)

    preview = commands.add_parser("preview")
    preview.add_argument("database_path")
    preview.add_argument("evidence_id", type=_evidence_id)
    preview.add_argument("artifact_path", nargs="?", default=None)
    preview.set_defaults(handler=_preview)

    timeline = commands.add_parser("timeline")
    timeline.add_argument("database_path")
    timeline.add_argument("case_id", type=_case_id)
    timeline.add_argument(
        "interval", nargs="?", default="day", choices=TIMELINE_INTERVALS
    )
    timeline.add_argument(
        "record_number", nargs="?", default=None, type=_record_number
    )
    timeline.set_defaults(handler=_timeline)

    regions = commands.add_parser("unallocated-regions")
    regions.add_argument("image_path")
    regions.add_argument("database_path")
    regions.add_argument("case_id", type=_case_id)
    regions.set_defaults(handler=_unallocated_regions)

    read = commands.add_parser("read-unallocated")
    read.add_argument("image_path")
    read.add_argument("database_path")
    read.add_argument("case_id", type=_case_id)
    read.add_argument("region_index", type=_region_index)
    read.add_argument("offset", type=_offset)
    read.add_argument("size", type=_size)
    read.set_defaults(handler=_read_unallocated)

    recover = commands.add_parser("recover-unallocated")
    recover.add_argument("image_path")
    recover.add_argument("database_path")
    recover.add_argument("case_id", type=_case_id)
    recover.set_defaults(handler=_recover_unallocated)

    recovered = commands.add_parser("recovered-artifacts")
    recovered.add_argument("database_path")
    recovered.add_argument("case_id", type=_case_id)
    recovered.set_defaults(handler=_recovered_artifacts)

    metafiles = commands.add_parser("metafiles")
    metafiles.add_argument("database_path")
    metafiles.add_argument("case_id", type=_case_id)
    metafiles.set_defaults(handler=_metafiles)

    carved_preview = commands.add_parser("recovered-preview")
    carved_preview.add_argument("image_path")
    carved_preview.add_argument("database_path")
    carved_preview.add_argument("case_id", type=_case_id)
    carved_preview.add_argument("artifact_id", type=_int_at_least(1, "artifact_id"))
    carved_preview.set_defaults(handler=_recovered_preview)

    carved_export = commands.add_parser("export-recovered")
    carved_export.add_argument("image_path")
    carved_export.add_argument("database_path")
    carved_export.add_argument("case_id", type=_case_id)
    carved_export.add_argument("destination")
    carved_export.add_argument("--ids", type=_record_list, default=None)
    carved_export.set_defaults(handler=_export_recovered)

    slack = commands.add_parser("file-slack")
    slack.add_argument("database_path")
    slack.add_argument("evidence_id", type=_evidence_id)
    slack.set_defaults(handler=_file_slack)

    deleted = commands.add_parser("deleted-files")
    deleted.add_argument("database_path")
    deleted.add_argument("case_id", type=_case_id)
    deleted.add_argument("--status", type=_status_list, default=None)
    deleted.set_defaults(handler=_deleted_files)

    restore = commands.add_parser("recover-deleted")
    restore.add_argument("image_path")
    restore.add_argument("database_path")
    restore.add_argument("case_id", type=_case_id)
    restore.add_argument("destination")
    restore.add_argument("--status", type=_status_list, default=None)
    restore.add_argument("--records", type=_record_list, default=None)
    restore.set_defaults(handler=_recover_deleted)

    extract = commands.add_parser("extract-metafiles")
    extract.add_argument("image_path")
    extract.add_argument("database_path")
    extract.add_argument("case_id", type=_case_id)
    extract.add_argument("destination")
    extract.set_defaults(handler=_extract_metafiles)

    return parser


# ---------------------------------------------------------------------
# Command handlers. Each returns a JSON-serialisable dict or raises.
# ---------------------------------------------------------------------

def _analyze(args):
    engine = _api("ForensicEngine")(
        case_name=args.case_name,
        investigator=args.investigator,
        cases_dir=args.cases_dir,
        description=args.description,
    )
    return engine.run(args.image_path).to_dictionary()


def _list_cases(args):
    return _api("CaseAPI")().list_cases(args.cases_dir)


def _version(args):
    import platform

    from engine.paths import DEFAULT_CASES_DIR
    from engine.version import ENGINE_VERSION

    return {
        "success": True,
        "engine_version": ENGINE_VERSION,
        "python_version": platform.python_version(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "cases_dir": str(DEFAULT_CASES_DIR),
    }


def _evidence(args):
    return _api("EvidenceAPI")().get_all_evidence(args.database_path, args.case_id)


def _filesystem(args):
    return _api("FilesystemAPI")().get_filesystem_tree(
        args.database_path, args.case_id
    )


def _preview(args):
    return _api("PreviewAPI")().get_preview(
        args.database_path, args.evidence_id, args.artifact_path
    )


def _timeline(args):
    return _api("TimelineAPI")().get_timeline(
        args.database_path, args.case_id, args.interval, args.record_number
    )


def _unallocated_regions(args):
    return _api("UnallocatedAPI")().list_regions(
        args.image_path, args.database_path, args.case_id
    )


def _read_unallocated(args):
    return _api("UnallocatedAPI")().read_region(
        args.image_path,
        args.database_path,
        args.case_id,
        args.region_index,
        args.offset,
        args.size,
    )


def _recover_unallocated(args):
    return _api("UnallocatedAPI")().recover(
        args.image_path, args.database_path, args.case_id
    )


def _recovered_artifacts(args):
    return _api("RecoveredArtifactAPI")().get_recovered_artifacts(
        args.database_path, args.case_id
    )


def _recovered_preview(args):
    return _api("RecoveredArtifactAPI")().preview(
        args.image_path, args.database_path, args.case_id, args.artifact_id
    )


def _export_recovered(args):
    return _api("RecoveredArtifactAPI")().export(
        args.image_path, args.database_path, args.case_id, args.destination, args.ids
    )


def _file_slack(args):
    return _api("SlackAPI")().file_slack(args.database_path, args.evidence_id)


def _deleted_files(args):
    return _api("DeletedFileAPI")().list_deleted(
        args.database_path, args.case_id, args.status
    )


def _recover_deleted(args):
    return _api("DeletedFileAPI")().recover_deleted(
        args.image_path, args.database_path, args.case_id, args.destination,
        args.status, args.records,
    )


def _metafiles(args):
    return _api("MetafileAPI")().list_metafiles(args.database_path, args.case_id)


def _extract_metafiles(args):
    return _api("MetafileAPI")().extract_metafiles(
        args.image_path, args.database_path, args.case_id, args.destination
    )


# ---------------------------------------------------------------------
# Output envelope
# ---------------------------------------------------------------------

def _failure_message(payload):
    """Pick a human-readable message from a handler's failure payload."""
    message = payload.get("error") or payload.get("message")
    if not message and payload.get("errors"):
        message = "; ".join(str(item) for item in payload["errors"])
    return str(message or "The command failed without an error message.")


def _write_json(payload):
    sys.stdout.write(json.dumps(payload, default=str))
    sys.stdout.write("\n")
    sys.stdout.flush()


def _report_error(command, error):
    if not isinstance(error, UsageError):
        traceback.print_exc(file=sys.stderr)

    _write_json({
        "success": False,
        "command": command,
        "error": str(error) or type(error).__name__,
        "error_type": getattr(error, "error_type", type(error).__name__),
    })
    return EXIT_USAGE if isinstance(error, UsageError) else EXIT_FAILURE


def main(argv=None):
    """Run one command and return the process exit code."""
    argv = sys.argv[1:] if argv is None else list(argv)
    command = argv[0] if argv else None

    try:
        if not argv:
            raise UsageError(
                "Usage: main_cli.py <command> [arguments] "
                "(no command supplied)"
            )

        args = build_parser().parse_args(argv)
        command = args.command

        # Library code prints progress with print(); keep stdout clean
        # so it holds only the JSON result.
        with redirect_stdout(sys.stderr):
            payload = args.handler(args)

        if not isinstance(payload, dict):
            raise TypeError(
                f"Command {command!r} returned {type(payload).__name__}, "
                "expected a JSON object"
            )

        if payload.get("success", True) is False:
            _write_json({
                **payload,
                "success": False,
                "command": command,
                "error": _failure_message(payload),
                "error_type": payload.get("error_type", "EngineError"),
            })
            return EXIT_FAILURE

        _write_json({"success": True, **payload})
        return EXIT_OK

    except Exception as error:
        return _report_error(command, error)


if __name__ == "__main__":
    sys.exit(main())
