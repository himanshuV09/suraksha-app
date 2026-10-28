from datetime import datetime, timedelta

def filetime_to_datetime(filetime):

    return datetime(1601, 1, 1) + timedelta(
        microseconds=filetime // 10
    )