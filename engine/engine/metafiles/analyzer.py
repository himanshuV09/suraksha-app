"""Run every NTFS metafile analyzer for one volume.

Produces:
  * one MetafileInfo per system metafile (records 0-11) and per
    $Extend child, with a metafile-specific ``details`` dict;
  * timeline events from the USN journal, $LogFile and $I30 ghosts.

Every analyzer is isolated: a damaged metafile yields status "error"
and a warning, never an exception, so the main analysis always finishes.
"""
import os
import re
from dataclasses import asdict, dataclass, field

from engine.metafiles.common import (
    ATTR_DATA,
    ATTR_STANDARD_INFORMATION,
    EXTEND_RECORD,
    SYSTEM_RECORDS,
    filetime_to_datetime,
    is_plausible,
)
from engine.metafiles.extend_files import EXTEND_DETAIL_PARSERS
from engine.metafiles.i30 import read_directory_index
from engine.metafiles.logfile import scan_logfile
from engine.metafiles.mft_slack import scan_mft_slack
from engine.metafiles.record import read_record_attributes
from engine.metafiles.stream import AttributeStream
from engine.metafiles.system_files import DETAIL_PARSERS
from engine.metafiles.usn_journal import (
    iter_usn_records,
    locate_usn_journal,
    summarize,
)
from engine.timeline.timeline_event import TimelineEvent

RESERVED_RECORDS = range(12, 24)
MAX_EXTEND_DEPTH = 4  # $Extend\$RmMetadata\$TxfLog\... is 3 deep

SOURCE_USN = "USN"
SOURCE_LOGFILE = "LOGFILE"
SOURCE_I30 = "I30"
SOURCE_MFT_SLACK = "MFT_SLACK"
ARTIFACT_TYPE = "Metafile"


@dataclass
class MetafileLimits:
    """Caps that keep one huge journal from flooding the timeline."""

    usn_events: int = 500_000
    logfile_entries: int = 200_000
    i30_ghosts: int = 200_000
    mft_slack_entries: int = 200_000
    i30_directories: int | None = None  # None = every directory


@dataclass
class MetafileInfo:
    record_number: int
    name: str
    status: str = "ok"  # "ok", "missing" or "error"
    in_use: bool | None = None
    directory: bool | None = None
    size: int = 0
    allocated_size: int = 0
    resident: bool | None = None
    fragments: int = 0
    streams: list = field(default_factory=list)
    created: object = None
    modified: object = None
    details: dict = field(default_factory=dict)
    error: str | None = None

    def to_dictionary(self):
        return asdict(self)


@dataclass
class MetafileReport:
    metafiles: list = field(default_factory=list)
    timeline_events: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    counts: dict = field(default_factory=dict)

    def find(self, name):
        return next((item for item in self.metafiles if item.name == name), None)

    @property
    def volume_label(self):
        volume = self.find("$Volume")
        return (volume.details.get("label") if volume else None) or ""


def walk_extend(parser, warnings=None):
    """Yield ("$Extend\\...\\name", record_number) for the whole $Extend tree.

    Depth-first, sorted by name, skipping 8.3 aliases and index loops.
    """
    visited = {EXTEND_RECORD}

    def walk(record_number, prefix, depth):
        try:
            entries = read_directory_index(parser, record_number, scan_slack=False).live
        except Exception as error:
            if warnings is not None:
                warnings.append(f"{prefix}: {error}")
            return
        for entry in sorted(entries, key=lambda item: item.key.name.lower()):
            if entry.key.namespace == 2 or entry.file_record in visited:
                continue
            visited.add(entry.file_record)
            name = f"{prefix}\\{entry.key.name}"
            yield name, entry.file_record
            if entry.key.is_directory and depth < MAX_EXTEND_DEPTH:
                yield from walk(entry.file_record, name, depth + 1)

    yield from walk(EXTEND_RECORD, "$Extend", 1)


class MetafileAnalyzer:

    def __init__(self, parser, limits=None):
        self.parser = parser
        self.limits = limits or MetafileLimits()
        self.paths = {
            evidence.record_number: evidence.full_path
            for evidence in parser.evidence_objects
            if evidence.full_path
        }

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def analyze(self, directory_records=None):
        """Analyze all metafiles; ``directory_records`` limits the $I30 scan.

        When omitted, directories known from MFT enumeration are scanned.
        """
        report = MetafileReport()
        report.counts.update({
            "usn_records": 0,
            "logfile_entries": 0,
            "i30_ghost_entries": 0,
        })

        for name, record_number in SYSTEM_RECORDS.items():
            report.metafiles.append(self._inventory(report, name, record_number))

        self._extend_tree(report)
        self._reserved_records(report)
        self._usn_journal(report)
        self._logfile(report)
        self._i30_ghosts(report, directory_records)
        self._mft_slack(report)
        self._add_paths(report)

        report.counts["metafiles"] = len(report.metafiles)
        report.counts["suspicious_reserved_records"] = sum(
            1 for item in report.metafiles if item.details.get("suspicious")
        )
        report.counts["timeline_events"] = len(report.timeline_events)
        return report

    # ------------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------------

    def _inventory(self, report, name, record_number, detail_parser=None):
        info = MetafileInfo(record_number=record_number, name=name)
        try:
            record = read_record_attributes(self.parser, record_number)
        except Exception as error:
            info.status = "missing"
            info.error = str(error)
            report.warnings.append(f"{name}: {error}")
            return info

        info.in_use = record.in_use
        info.directory = record.directory
        info.streams = record.streams()

        standard = record.find(ATTR_STANDARD_INFORMATION)
        if standard is not None and standard.resident and len(standard.content) >= 16:
            info.created = filetime_to_datetime(int.from_bytes(standard.content[0:8], "little"))
            info.modified = filetime_to_datetime(int.from_bytes(standard.content[8:16], "little"))

        data = record.find(ATTR_DATA)
        if data is None and info.streams:
            data = record.find(ATTR_DATA, info.streams[0]["name"])
        if data is not None:
            info.size = data.size
            info.allocated_size = data.allocated_size if not data.resident else data.size
            info.resident = data.resident
            info.fragments = data.fragment_count

        detail_parser = detail_parser or DETAIL_PARSERS.get(name)
        if detail_parser is not None:
            try:
                info.details = detail_parser(self.parser, record)
            except Exception as error:
                info.status = "error"
                info.error = f"{type(error).__name__}: {error}"
                report.warnings.append(f"{name}: {info.error}")

        for warning in record.warnings:
            report.warnings.append(f"{name}: {warning}")

        return info

    def _extend_tree(self, report):
        """Inventory everything under $Extend ($RmMetadata\\$TxfLog\\... too)."""
        for name, record_number in walk_extend(self.parser, report.warnings):
            report.metafiles.append(self._inventory(
                report, name, record_number,
                EXTEND_DETAIL_PARSERS.get(name.rsplit("\\", 1)[-1]),
            ))

    def _reserved_records(self, report):
        """Records 12-23 are reserved by NTFS and normally hold no data.

        Data stored there is invisible to Explorer and most tools, which
        makes it a known hiding place. Records 16-23 may legitimately hold
        $MFT extension records (base record 0).
        """
        for record_number in RESERVED_RECORDS:
            try:
                record = read_record_attributes(self.parser, record_number)
            except Exception:
                continue  # unused slot: nothing to report

            streams = record.streams()
            data_bytes = sum(stream["size"] for stream in streams)
            extension_of_mft = record.base_record == 0 and record_number >= 16
            suspicious = record.in_use and data_bytes > 0 and not extension_of_mft
            info = MetafileInfo(
                record_number=record_number,
                name=f"[Reserved {record_number}]",
                in_use=record.in_use,
                directory=record.directory,
                size=data_bytes,
                streams=streams,
                details={
                    "reserved": True,
                    "base_record": record.base_record,
                    "data_bytes": data_bytes,
                    "suspicious": suspicious,
                    "reason": (
                        "reserved record contains data" if suspicious else None
                    ),
                },
            )
            report.metafiles.append(info)
            if suspicious:
                report.warnings.append(
                    f"Reserved MFT record {record_number} holds {data_bytes} bytes of data"
                )

    def _mft_slack(self, report):
        """Names of earlier files left in the unused tail of MFT records."""
        live = {}
        current = {}
        for evidence in self.parser.evidence_objects:
            if evidence.filename:
                live.setdefault(evidence.record_number, set()).add(
                    (evidence.filename.lower(), evidence.parent_record)
                )
                current[evidence.record_number] = evidence.full_path or evidence.filename
        try:
            entries, scanned, truncated = scan_mft_slack(
                self.parser, live, self.limits.mft_slack_entries
            )
        except Exception as error:
            report.warnings.append(f"MFT slack scan: {type(error).__name__}: {error}")
            return

        report.counts.update({
            "mft_slack_records_scanned": scanned,
            "mft_slack_entries": len(entries),
            "mft_slack_truncated": truncated,
        })
        for entry in entries:
            now = current.get(entry.record_number, "unused")
            detail = (
                f"Earlier $FILE_NAME left in slack of MFT record {entry.record_number} "
                f"(record now holds: {now})"
            )
            for timestamp, event_type in self._key_times(entry.key):
                report.timeline_events.append(TimelineEvent(
                    record_number=entry.record_number,
                    filename=entry.key.name,
                    full_path=self._child_path(entry.key.parent_record, entry.key.name),
                    timestamp=timestamp,
                    event_type=event_type,
                    deleted=True,
                    directory=entry.key.is_directory,
                    source=SOURCE_MFT_SLACK,
                    artifact_type=ARTIFACT_TYPE,
                    description=detail,
                ))

    def _add_paths(self, report):
        """Add file paths to listed entries that only carry a record number."""
        for item in report.metafiles:
            for entry in item.details.get("entries", []) or []:
                if isinstance(entry, dict) and "record_number" in entry:
                    path = self.paths.get(entry["record_number"])
                    if path:
                        entry["path"] = path

    # ------------------------------------------------------------------
    # Journals
    # ------------------------------------------------------------------

    def _usn_journal(self, report):
        target = report.find("$Extend\\$UsnJrnl")
        try:
            journal, j_stream = locate_usn_journal(self.parser)
        except Exception as error:
            report.warnings.append(f"$UsnJrnl: {error}")
            return
        if journal is None:
            report.counts["usn_records"] = 0
            return

        details = {
            "j_size": journal.j_size,
            "j_allocated_size": journal.j_allocated_size,
            "j_fragments": journal.j_fragments,
            "max_size": journal.max_size,
            "allocation_delta": journal.allocation_delta,
            "journal_id": journal.journal_id,
            "lowest_valid_usn": journal.lowest_valid_usn,
        }

        if j_stream is not None:
            try:
                stream = AttributeStream(self.parser.image, self.parser.geometry, j_stream)
                records, summary = summarize(
                    iter_usn_records(stream.segments()), self.limits.usn_events
                )
                details.update(summary)
                for record in records:
                    event = self._usn_event(record)
                    if event is not None:
                        report.timeline_events.append(event)
            except Exception as error:
                details["error"] = f"{type(error).__name__}: {error}"
                report.warnings.append(f"$UsnJrnl:$J: {details['error']}")

        report.counts["usn_records"] = details.get("record_count", 0)
        if target is not None:
            target.details.update(details)

    def _usn_event(self, record):
        if not is_plausible(record.timestamp):
            return None
        return TimelineEvent(
            record_number=record.file_record,
            filename=record.name,
            full_path=self._child_path(record.parent_record, record.name),
            timestamp=record.timestamp,
            event_type=record.action,
            deleted=record.action == "Deleted",
            directory=record.is_directory,
            source=SOURCE_USN,
            artifact_type=ARTIFACT_TYPE,
            description=f"USN {record.usn}: " + "|".join(record.reasons),
        )

    def _logfile(self, report):
        target = report.find("$LogFile")
        try:
            record = read_record_attributes(self.parser, SYSTEM_RECORDS["$LogFile"])
            data = record.find(ATTR_DATA)
            if data is None:
                raise ValueError("$LogFile has no $DATA stream")
            scan = scan_logfile(
                AttributeStream(self.parser.image, self.parser.geometry, data),
                self.limits.logfile_entries,
            )
        except Exception as error:
            message = f"{type(error).__name__}: {error}"
            report.warnings.append(f"$LogFile scan: {message}")
            if target is not None:
                target.details["error"] = message
            return

        if target is not None:
            target.details.update(scan.as_details())
        report.counts["logfile_entries"] = len(scan.entries)

        for key in scan.entries:
            path = self._child_path(key.parent_record, key.name)
            detail = f"$LogFile $FILE_NAME (parent record {key.parent_record})"
            for timestamp, event_type in self._key_times(key):
                report.timeline_events.append(TimelineEvent(
                    record_number=None,
                    filename=key.name,
                    full_path=path,
                    timestamp=timestamp,
                    event_type=event_type,
                    directory=key.is_directory,
                    source=SOURCE_LOGFILE,
                    artifact_type=ARTIFACT_TYPE,
                    description=detail,
                ))

    # ------------------------------------------------------------------
    # $I30 ghosts
    # ------------------------------------------------------------------

    def _i30_ghosts(self, report, directory_records):
        if directory_records is None:
            directory_records = [
                evidence.record_number
                for evidence in self.parser.evidence_objects
                if evidence.directory and not evidence.deleted
            ]
        if self.limits.i30_directories is not None:
            directory_records = directory_records[:self.limits.i30_directories]

        scanned = failed = ghosts = 0
        for record_number in directory_records:
            if ghosts >= self.limits.i30_ghosts:
                break
            try:
                index = read_directory_index(self.parser, record_number)
            except Exception:
                failed += 1
                continue
            scanned += 1
            for entry in index.ghosts:
                ghosts += 1
                self._add_ghost(report, entry)

        report.counts.update({
            "i30_directories_scanned": scanned,
            "i30_directories_failed": failed,
            "i30_ghost_entries": ghosts,
        })

    def _add_ghost(self, report, entry):
        key = entry.key
        directory = self.paths.get(entry.directory_record, f"[record {entry.directory_record}]")
        detail = (
            f"Deleted entry recovered from $I30 {entry.location} "
            f"of {directory}"
        )
        for timestamp, event_type in self._key_times(key):
            report.timeline_events.append(TimelineEvent(
                record_number=entry.file_record or None,
                filename=key.name,
                full_path=self._child_path(key.parent_record, key.name),
                timestamp=timestamp,
                event_type=event_type,
                deleted=True,
                directory=key.is_directory,
                source=SOURCE_I30,
                artifact_type=ARTIFACT_TYPE,
                description=detail,
            ))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _key_times(key):
        """Created and (if different) Modified times of a $FILE_NAME key."""
        times = []
        if is_plausible(key.created):
            times.append((key.created, "Created"))
        if is_plausible(key.modified) and key.modified != key.created:
            times.append((key.modified, "Modified"))
        return times

    def _child_path(self, parent_record, name):
        parent = self.paths.get(parent_record)
        return f"{parent}/{name}" if parent else name


# ----------------------------------------------------------------------
# Raw export ("Extract All", as FTK Imager does for NTFS metadata)
# ----------------------------------------------------------------------

def _safe_filename(name):
    # "$Extend\$UsnJrnl" -> "_Extend__UsnJrnl"
    return re.sub(r'[\\/:*?"<>|$]', "_", name)


def export_metafiles(parser, destination, include_streams=True):
    """Copy every metafile's raw streams into ``destination``.

    Unnamed streams are written as ``_MFT``; named streams as
    ``_UsnJrnl__J``. Returns one entry per written file.
    """
    os.makedirs(destination, exist_ok=True)

    targets = [(name, number) for name, number in SYSTEM_RECORDS.items() if name != "."]
    targets += list(walk_extend(parser))

    exported = []
    for name, record_number in targets:
        try:
            record = read_record_attributes(parser, record_number)
        except Exception as error:
            exported.append({"name": name, "record_number": record_number, "error": str(error)})
            continue

        for attribute in record.find_all(ATTR_DATA):
            if attribute.name and not include_streams:
                continue
            filename = _safe_filename(name.split("\\")[-1])
            if attribute.name:
                filename += "_" + _safe_filename(attribute.name)
            path = os.path.join(destination, filename)
            entry = {
                "name": name + (f":{attribute.name}" if attribute.name else ""),
                "record_number": record_number,
            }
            try:
                stream = AttributeStream(parser.image, parser.geometry, attribute)
                if stream.size and not stream.has_data:
                    # e.g. $BadClus:$Bad: as large as the volume, all sparse.
                    entry["skipped"] = (
                        f"entirely sparse ({stream.size} bytes, no data on disk)"
                    )
                else:
                    with open(path, "wb") as handle:
                        entry["size"] = stream.copy_to(handle)
                    entry["path"] = os.path.abspath(path)
            except Exception as error:
                entry["error"] = f"{type(error).__name__}: {error}"
            exported.append(entry)

    return exported
