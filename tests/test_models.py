"""Tests for data models and to_episode_content()."""
from datetime import datetime, timezone

import pytest

from models.base import CommunicationDirection
from models.call_transcript import CallTranscript
from models.email import Email, EmailDirection
from models.meeting_notes import MeetingNotes
from models.social_engagement import SocialEngagement
from models.text_message import TextMessage


class TestEmail:
    def test_to_episode_content(self):
        email = Email(
            message_id="msg-1",
            from_email="alice@acme.com",
            from_name="Alice",
            to_emails=["bob@ourco.com"],
            subject="Partnership proposal",
            body_text="Hi Bob, let's discuss a partnership.",
            timestamp=datetime(2026, 3, 15, tzinfo=timezone.utc),
            direction=EmailDirection.INBOUND,
        )
        content = email.to_episode_content()
        assert "Partnership proposal" in content
        assert "alice@acme.com" in content
        assert "bob@ourco.com" in content

    def test_get_external_participants(self):
        email = Email(
            message_id="msg-2",
            from_email="alice@acme.com",
            to_emails=["bob@ourco.com", "carol@acme.com"],
            subject="Test",
            body_text="Test",
            timestamp=datetime(2026, 3, 15, tzinfo=timezone.utc),
            direction=EmailDirection.INBOUND,
        )
        external = email.get_external_participants(["ourco.com"])
        assert "alice@acme.com" in external
        assert "carol@acme.com" in external
        assert "bob@ourco.com" not in external

    def test_from_domain_property(self):
        email = Email(
            message_id="msg-3",
            from_email="alice@acme.com",
            to_emails=["bob@ourco.com"],
            subject="Test",
            body_text="Test",
            timestamp=datetime(2026, 3, 15, tzinfo=timezone.utc),
            direction=EmailDirection.INBOUND,
        )
        assert email.from_domain == "acme.com"


class TestCallTranscript:
    def test_to_episode_content(self):
        call = CallTranscript(
            call_id="call-1",
            provider="gong",
            caller="Sarah Johnson",
            callee="John Smith",
            timestamp=datetime(2026, 3, 15, tzinfo=timezone.utc),
            duration_minutes=30.0,
            title="Q1 Renewal Discussion",
            transcript="Sarah: Hi John, let's discuss renewal.\nJohn: Sure.",
            direction=CommunicationDirection.OUTBOUND,
            account_name="Acme Corp",
        )
        content = call.to_episode_content()
        assert "Call Transcript Record" in content
        assert "Sarah Johnson" in content
        assert "John Smith" in content
        assert "30 minutes" in content
        assert "gong" in content

    def test_to_episode_content_truncation(self):
        call = CallTranscript(
            call_id="call-2",
            provider="zoom",
            caller="A",
            callee="B",
            timestamp=datetime(2026, 3, 15, tzinfo=timezone.utc),
            transcript="x" * 15000,
            direction=CommunicationDirection.INBOUND,
        )
        content = call.to_episode_content()
        assert len(content) <= 10500  # 10000 + some header


class TestTextMessage:
    def test_to_episode_content(self):
        msg = TextMessage(
            message_id="txt-1",
            provider="twilio",
            from_identifier="+15551234567",
            to_identifier="+15559876543",
            body="Thanks for the pricing info!",
            timestamp=datetime(2026, 3, 15, tzinfo=timezone.utc),
            direction=CommunicationDirection.INBOUND,
            channel="sms",
            account_name="Acme Corp",
        )
        content = msg.to_episode_content()
        assert "Text Message Record" in content
        assert "+15551234567" in content
        assert "Thanks for the pricing info!" in content
        assert "sms" in content


class TestSocialEngagement:
    def test_to_episode_content_message(self):
        engagement = SocialEngagement(
            engagement_id="se-1",
            platform="linkedin",
            from_user="alice@linkedin",
            to_user="bob@linkedin",
            activity_type="message",
            content="Great connecting with you!",
            timestamp=datetime(2026, 3, 15, tzinfo=timezone.utc),
            direction=CommunicationDirection.OUTBOUND,
        )
        content = engagement.to_episode_content()
        assert "Social Engagement Record" in content
        assert "linkedin" in content
        assert "message" in content

    def test_to_episode_content_like(self):
        engagement = SocialEngagement(
            engagement_id="se-2",
            platform="twitter",
            from_user="our_team",
            to_user="prospect",
            activity_type="like",
            target_content="Their post about AI trends in 2026",
            timestamp=datetime(2026, 3, 15, tzinfo=timezone.utc),
            direction=CommunicationDirection.OUTBOUND,
        )
        content = engagement.to_episode_content()
        assert "twitter" in content
        assert "like" in content
        assert "AI trends" in content


class TestMeetingNotes:
    def test_to_episode_content(self):
        meeting = MeetingNotes(
            meeting_id="meet-1",
            provider="google_calendar",
            title="Q1 Strategy Review",
            organizer="Sarah Johnson",
            attendees=["John Smith", "Jane Doe", "Bob Wilson"],
            start_time=datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 15, 15, 0, tzinfo=timezone.utc),
            notes="Discussed Q1 targets and renewal pipeline.",
            account_name="Acme Corp",
        )
        content = meeting.to_episode_content()
        assert "Meeting Record" in content
        assert "Q1 Strategy Review" in content
        assert "60 minutes" in content
        assert "Sarah Johnson" in content
        assert "John Smith" in content

    def test_to_episode_content_no_end_time(self):
        meeting = MeetingNotes(
            meeting_id="meet-2",
            provider="calendly",
            title="Intro Call",
            organizer="Bob",
            attendees=["Alice"],
            start_time=datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc),
            notes="Brief intro.",
        )
        content = meeting.to_episode_content()
        assert "Meeting Record" in content
        assert "minutes" not in content  # No duration without end_time
