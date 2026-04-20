"""Ingest pipeline: URL or file -> extracted text -> Claude-drafted Source+Claims+Evidence."""

from afls.ingest.fetch import MIN_PARAGRAPH_TAGS, fetch_and_extract
from afls.ingest.read import (
    SUPPORTED_SUFFIXES,
    ReadResult,
    UnsupportedFileType,
    read_and_extract,
)

__all__ = [
    "MIN_PARAGRAPH_TAGS",
    "SUPPORTED_SUFFIXES",
    "ReadResult",
    "UnsupportedFileType",
    "fetch_and_extract",
    "read_and_extract",
]
