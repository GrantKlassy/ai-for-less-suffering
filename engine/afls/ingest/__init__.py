"""Ingest pipeline: URL -> fetched text -> Claude-drafted Source+Claims+Evidence."""

from afls.ingest.fetch import MIN_PARAGRAPH_TAGS, fetch_and_extract

__all__ = ["MIN_PARAGRAPH_TAGS", "fetch_and_extract"]
