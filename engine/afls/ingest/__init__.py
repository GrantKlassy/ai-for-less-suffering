"""Ingest pipeline: URL -> fetched text -> Claude-drafted Source+Claims+Evidence."""

from afls.ingest.fetch import fetch_and_extract

__all__ = ["fetch_and_extract"]
