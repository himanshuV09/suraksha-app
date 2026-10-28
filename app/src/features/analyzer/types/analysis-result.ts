export interface AnalysisResult {
  success: boolean;
  message: string;

  case_id: number;

  case_name?: string;

  investigator?: string;

  image_path: string;

  /** Absolute path of the case database; use it for every later command. */
  database_path: string;

  filesystem: string;

  volume_label: string;

  serial_number: string;

  image_size: number;

  cluster_size: number;

  sector_size: number;

  total_records: number;

  total_files: number;

  total_directories: number;

  deleted_files: number;

  fragmented_files: number;

  fragment_count: number;

  ads_files: number;

  slack_files: number;

  high_risk_files: number;

  timeline_events: number;

  /** MFT records that were malformed and skipped. */
  corrupt_records: number;

  record_error_count: number;

  /** The first skipped records and why they could not be parsed. */
  record_errors: { record_number: number; error: string }[];

  /** Problems that did not stop the analysis. */
  warnings: string[];

  /** NTFS metafile results, e.g. usn_records, logfile_entries, i30_ghost_entries. */
  metafile_counts: Record<string, number>;

  /** Deleted files graded during analysis: deleted_recoverable, deleted_partial, ... */
  deleted_recovery: Record<string, number>;

  duration: number;

  errors: string[];
}