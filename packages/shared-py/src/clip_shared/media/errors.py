from dataclasses import dataclass
from typing import Any


@dataclass
class FriendlyErrorDetail:
    code: str
    title: str
    what_happened: str
    what_to_do: str
    can_retry: bool
    action_label: str = "Retry"
    support_action: bool = True


ERROR_TAXONOMY: dict[str, FriendlyErrorDetail] = {
    "NO_AUDIO": FriendlyErrorDetail(
        code="NO_AUDIO",
        title="No Audio Detected",
        what_happened="The uploaded video does not contain any usable audio or speech track.",
        what_to_do="Please upload a video with clearly audible speech, or verify that your audio stream is enabled.",
        can_retry=False,
    ),
    "UNSUPPORTED_CODEC": FriendlyErrorDetail(
        code="UNSUPPORTED_CODEC",
        title="Unsupported Video Format",
        what_happened="The file uses a video or audio codec that cannot be parsed by our media pipeline.",
        what_to_do="Please convert your video to standard H.264 MP4, MOV, or WebM and try again.",
        can_retry=False,
    ),
    "CORRUPT_FILE": FriendlyErrorDetail(
        code="CORRUPT_FILE",
        title="Damaged File",
        what_happened="The uploaded file appears corrupted or incomplete.",
        what_to_do="Verify that the file plays properly on your computer, then re-upload.",
        can_retry=False,
    ),
    "TOO_LONG": FriendlyErrorDetail(
        code="TOO_LONG",
        title="Duration Exceeds Plan Limit",
        what_happened="The source video duration is longer than your plan's maximum length.",
        what_to_do="Trim your source video or upgrade to Creator or Pro Studio for up to 120 minutes.",
        can_retry=False,
    ),
    "TRANSCRIBE_FAILED": FriendlyErrorDetail(
        code="TRANSCRIBE_FAILED",
        title="Speech Recognition Interrupted",
        what_happened="The speech-to-text transcription engine was temporarily interrupted.",
        what_to_do="Click Retry to resume transcription from this stage without losing progress.",
        can_retry=True,
    ),
    "LLM_UNAVAILABLE": FriendlyErrorDetail(
        code="LLM_UNAVAILABLE",
        title="AI Scoring Service Unavailable",
        what_happened="The Claude AI scoring API was temporarily unreachable.",
        what_to_do="Click Retry to re-run AI evaluation, or continue with acoustic heuristic ranking.",
        can_retry=True,
    ),
    "RENDER_FAILED": FriendlyErrorDetail(
        code="RENDER_FAILED",
        title="Export Render Interrupted",
        what_happened="The video rendering worker encountered a temporary encoding glitch.",
        what_to_do="Click Retry Export to regenerate the vertical clip.",
        can_retry=True,
    ),
    "PLAN_LIMIT_EXCEEDED": FriendlyErrorDetail(
        code="PLAN_LIMIT_EXCEEDED",
        title="Monthly Quota Limit Reached",
        what_happened="You have consumed your monthly allotment of source minutes or exports.",
        what_to_do="Upgrade your subscription or buy an instant top-up minute pack to keep going.",
        can_retry=False,
        action_label="Upgrade Plan",
    ),
    "CONCURRENCY_LIMIT": FriendlyErrorDetail(
        code="CONCURRENCY_LIMIT",
        title="Concurrent Jobs Limit Reached",
        what_happened="Your plan allows a limited number of simultaneous jobs.",
        what_to_do="Wait for your current jobs to finish, or upgrade to Pro for higher concurrency.",
        can_retry=True,
    ),
    "INTERNAL": FriendlyErrorDetail(
        code="INTERNAL",
        title="Unexpected Pipeline Error",
        what_happened="An internal server error occurred while processing your video.",
        what_to_do="Click Retry, or click Report a Problem to notify engineering with your Job ID.",
        can_retry=True,
        action_label="Retry Stage",
    ),
}


def get_friendly_error(code: str) -> dict[str, Any]:
    """Retrieve structured user-facing error guidance from error taxonomy."""
    clean_code = code.upper().strip("[] ")
    err = ERROR_TAXONOMY.get(clean_code, ERROR_TAXONOMY["INTERNAL"])
    return {
        "code": err.code,
        "title": err.title,
        "what_happened": err.what_happened,
        "what_to_do": err.what_to_do,
        "can_retry": err.can_retry,
        "action_label": err.action_label,
        "support_action": err.support_action,
    }
