"""
Helpers to resolve ingest requests into episode content.
"""
from datetime import datetime, timezone
from typing import Tuple, Union

from api.models import BulkIngestItem, IngestMode, IngestRequest
from models import CallTranscript, Email, MeetingNotes, SocialEngagement, TextMessage

MODEL_MAP = {
    IngestMode.EMAIL: Email,
    IngestMode.CALL: CallTranscript,
    IngestMode.TEXT_MSG: TextMessage,
    IngestMode.SOCIAL: SocialEngagement,
    IngestMode.MEETING: MeetingNotes,
}


def resolve_episode(
    item: Union[IngestRequest, BulkIngestItem],
    account_name: str,
) -> Tuple[str, str, str, datetime]:
    """
    Resolve an ingest item into (content, name, source_description, reference_time).

    For raw mode: uses content/name/source_description directly.
    For structured mode: instantiates the model and calls to_episode_content().

    Returns
    -------
    tuple of (content, name, source_description, reference_time)

    Raises
    ------
    ValueError
        If required fields are missing for the given mode.
    """
    if item.mode == IngestMode.RAW:
        if not item.content:
            raise ValueError("content is required for mode=raw")
        return (
            item.content,
            item.name or "Raw episode",
            item.source_description or "Direct API ingestion",
            item.reference_time or datetime.now(timezone.utc),
        )

    # Structured mode
    model_cls = MODEL_MAP.get(item.mode)
    if not model_cls:
        raise ValueError(f"Unsupported mode: {item.mode}")

    if not item.data:
        raise ValueError(f"data is required for mode={item.mode.value}")

    model_instance = model_cls(**item.data)

    # Set account_name on the model if it has the field
    if hasattr(model_instance, "account_name"):
        model_instance.account_name = account_name

    content = model_instance.to_episode_content()

    # Derive episode name from the model
    name = item.name or _build_name(item.mode, model_instance)
    source_description = item.source_description or _build_source_desc(item.mode, model_instance)

    # Get reference_time from model's timestamp field
    ref_time = item.reference_time
    if not ref_time:
        ref_time = (
            getattr(model_instance, "timestamp", None)
            or getattr(model_instance, "start_time", None)
            or datetime.now(timezone.utc)
        )

    return (content, name, source_description, ref_time)


def _build_name(mode: IngestMode, model) -> str:
    """Build a human-readable episode name from a model instance."""
    if mode == IngestMode.EMAIL:
        return f"Email: {getattr(model, 'subject', '')[:50]}"
    if mode == IngestMode.CALL:
        title = getattr(model, "title", None) or "Untitled"
        return f"Call: {title[:50]}"
    if mode == IngestMode.TEXT_MSG:
        return f"Text: {getattr(model, 'body', '')[:50]}"
    if mode == IngestMode.SOCIAL:
        return f"Social: {getattr(model, 'activity_type', '')} on {getattr(model, 'platform', '')}"
    if mode == IngestMode.MEETING:
        return f"Meeting: {getattr(model, 'title', '')[:50]}"
    return f"{mode.value} episode"


def _build_source_desc(mode: IngestMode, model) -> str:
    """Build a source description from the model."""
    direction = getattr(model, "direction", None)
    direction_str = f" ({direction.value})" if direction else ""
    return f"{mode.value}{direction_str}"
