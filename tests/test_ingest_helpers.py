"""Tests for API ingest helper functions."""
from datetime import datetime, timezone

import pytest

from api.ingest_helpers import resolve_episode
from api.models import BulkIngestItem, IngestMode, IngestRequest


class TestResolveEpisodeRaw:
    def test_raw_mode(self):
        req = IngestRequest(
            account_name="Acme",
            mode=IngestMode.RAW,
            content="Call with John about renewal",
            name="Call: John renewal",
            source_description="call (outbound)",
            reference_time=datetime(2026, 3, 15, tzinfo=timezone.utc),
        )
        content, name, source_desc, ref_time = resolve_episode(req, "Acme")
        assert content == "Call with John about renewal"
        assert name == "Call: John renewal"
        assert source_desc == "call (outbound)"
        assert ref_time == datetime(2026, 3, 15, tzinfo=timezone.utc)

    def test_raw_mode_defaults(self):
        req = IngestRequest(
            account_name="Acme",
            mode=IngestMode.RAW,
            content="Some content",
        )
        content, name, source_desc, ref_time = resolve_episode(req, "Acme")
        assert content == "Some content"
        assert name == "Raw episode"
        assert source_desc == "Direct API ingestion"
        assert ref_time is not None

    def test_raw_mode_missing_content_raises(self):
        req = IngestRequest(account_name="Acme", mode=IngestMode.RAW)
        with pytest.raises(ValueError, match="content is required"):
            resolve_episode(req, "Acme")


class TestResolveEpisodeStructured:
    def test_email_mode(self):
        req = IngestRequest(
            account_name="Acme",
            mode=IngestMode.EMAIL,
            data={
                "message_id": "msg-1",
                "from_email": "sarah@ourco.com",
                "to_emails": ["john@acme.com"],
                "subject": "Follow up",
                "body_text": "Hi John",
                "timestamp": "2026-03-15T16:00:00Z",
                "direction": "outbound",
            },
        )
        content, name, source_desc, ref_time = resolve_episode(req, "Acme")
        assert "Follow up" in content
        assert "Email:" in name
        assert "email" in source_desc

    def test_call_mode(self):
        req = IngestRequest(
            account_name="Acme",
            mode=IngestMode.CALL,
            data={
                "call_id": "call-1",
                "provider": "gong",
                "caller": "Sarah",
                "callee": "John",
                "timestamp": "2026-03-15T14:00:00Z",
                "transcript": "Hello, let's discuss the deal.",
                "direction": "outbound",
            },
        )
        content, name, source_desc, ref_time = resolve_episode(req, "Acme")
        assert "Call Transcript Record" in content
        assert "Call:" in name

    def test_structured_missing_data_raises(self):
        req = IngestRequest(account_name="Acme", mode=IngestMode.EMAIL)
        with pytest.raises(ValueError, match="data is required"):
            resolve_episode(req, "Acme")


class TestResolveEpisodeBulkItem:
    def test_bulk_item_raw(self):
        item = BulkIngestItem(
            mode=IngestMode.RAW,
            content="LinkedIn connect from Jane",
            name="Social: connect",
            source_description="linkedin",
        )
        content, name, source_desc, ref_time = resolve_episode(item, "Acme")
        assert content == "LinkedIn connect from Jane"
        assert name == "Social: connect"

    def test_bulk_item_reference_time_from_model(self):
        item = BulkIngestItem(
            mode=IngestMode.MEETING,
            data={
                "meeting_id": "meet-1",
                "provider": "google_calendar",
                "title": "Strategy Review",
                "organizer": "Sarah",
                "attendees": ["John"],
                "start_time": "2026-03-15T14:00:00Z",
                "notes": "Discussed targets.",
            },
        )
        content, name, source_desc, ref_time = resolve_episode(item, "Acme")
        assert ref_time == datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc)
        assert "Meeting:" in name
