"""NTFS metafile parsing.

    analyzer.py      run everything for one volume (MetafileAnalyzer)
    system_files.py  summaries of records 0-11 ($MFT ... $Extend)
    usn_journal.py   $Extend\\$UsnJrnl:$J change journal
    logfile.py       $LogFile transaction journal
    i30.py           directory indexes, including deleted entries
    record.py        all attributes of a record (follows $ATTRIBUTE_LIST)
    stream.py        read any attribute's bytes (sparse-aware)
    common.py        record numbers, FILETIME and $FILE_NAME decoding

Approach follows the forensicx reference implementation
(H:\\GUI_updated_collection\\forensicx, core/ntfs and core/timeline).
"""
