import asyncio
import os
from datetime import datetime
from typing import Annotated

from mcp.server.mcpserver import Resolve
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from moodler_mcp import cache
from moodler_mcp import moodle_api as api
from moodler_mcp.asking import NO_APPROVAL, Approval, approval
from moodler_mcp.client import call, upload_draft
from moodler_mcp.results import result
from moodler_mcp.server import mcp

WRITE = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=False
)
SAFE_WRITE = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)

NOT_CONFIRMED = "Not executed. Call again with confirm=true to proceed: "


class WriteResult(BaseModel):
    executed: bool
    detail: str
    ids: dict[str, int] = {}


def _preview(text: str) -> WriteResult:
    return WriteResult(executed=False, detail=text)


def _ts(iso_value: str) -> int:
    return int(datetime.fromisoformat(iso_value).timestamp())


@mcp.tool(title="Submit assignment", annotations=WRITE)
async def submit_assignment(
    assign_id: int,
    file_path: str,
    confirm: bool = False,
    approval_: Annotated[
        Approval, Resolve(approval("Submit this file to the assignment for grading?"))
    ] = NO_APPROVAL,
) -> WriteResult:
    """Upload a file as your submission for an assignment and submit it for grading.
    Replaces any existing draft files. Requires confirm=true.

    Args:
        assign_id: Assignment instance id (from list_assignments)
        file_path: Absolute path of the file to submit
        confirm: Must be true to execute
    """
    if not os.path.isfile(file_path):
        raise ToolError(f"No such file: {file_path}")
    summary = f"submit {os.path.basename(file_path)} to assignment {assign_id}"
    if not (confirm or approval_.confirm):
        return result(NOT_CONFIRMED + summary, _preview(summary))
    status = await api.submission_status(assign_id=assign_id)
    if not (status.get("lastattempt") or {}).get("cansubmit", True):
        raise ToolError(f"Assignment {assign_id} does not accept a submission from you right now")
    item_id = await upload_draft(file_path)
    await call(
        "mod_assign_save_submission",
        assignmentid=assign_id,
        plugindata={"files_filemanager": item_id},
    )
    await call(
        "mod_assign_submit_for_grading", assignmentid=assign_id, acceptsubmissionstatement=True
    )
    await asyncio.to_thread(cache.clear, f'submission_status:{{"assign_id": {assign_id}}}')
    out = WriteResult(
        executed=True,
        detail=f"Submitted {os.path.basename(file_path)} for grading.",
        ids={"assign_id": assign_id, "draft_item_id": item_id},
    )
    return result(out.detail, out)


@mcp.tool(title="Reply in forum", annotations=WRITE)
async def post_forum_reply(
    post_id: int,
    subject: str,
    message: str,
    confirm: bool = False,
    approval_: Annotated[
        Approval, Resolve(approval("Post this reply to the forum?"))
    ] = NO_APPROVAL,
) -> WriteResult:
    """Post a reply to a forum post. Requires confirm=true.

    Args:
        post_id: The post to reply to (first_post_id from list_discussions, or post_id from get_discussion)
        subject: Reply subject
        message: Reply body, plain text or HTML
        confirm: Must be true to execute
    """
    summary = f"reply to post {post_id} with subject '{subject}'"
    if not (confirm or approval_.confirm):
        return result(NOT_CONFIRMED + summary, _preview(summary))
    data = await call(
        "mod_forum_add_discussion_post",
        postid=post_id,
        subject=subject,
        message=message,
        messageformat=1,
    )
    out = WriteResult(
        executed=True,
        detail=f"Posted reply {data.get('postid')}.",
        ids={"post_id": int(data.get("postid") or 0)},
    )
    return result(out.detail, out)


@mcp.tool(title="Reply to conversation", annotations=WRITE)
async def reply_to_conversation(
    conversation_id: int,
    message: str,
    confirm: bool = False,
    approval_: Annotated[Approval, Resolve(approval("Send this message?"))] = NO_APPROVAL,
) -> WriteResult:
    """Send a message in an existing conversation. Requires confirm=true.

    Args:
        conversation_id: From list_conversations
        message: Plain text message
        confirm: Must be true to execute
    """
    summary = f"send '{message[:60]}' to conversation {conversation_id}"
    if not (confirm or approval_.confirm):
        return result(NOT_CONFIRMED + summary, _preview(summary))
    data = await call(
        "core_message_send_messages_to_conversation",
        conversationid=conversation_id,
        messages=[{"text": message, "textformat": 0}],
    )
    sent = data[0] if isinstance(data, list) and data else {}
    out = WriteResult(
        executed=True, detail="Message sent.", ids={"message_id": int(sent.get("id") or 0)}
    )
    return result(out.detail, out)


@mcp.tool(title="Mark notifications read", annotations=WRITE)
async def mark_notifications_read(
    confirm: bool = False,
    approval_: Annotated[
        Approval, Resolve(approval("Mark every notification as read? This cannot be undone."))
    ] = NO_APPROVAL,
) -> WriteResult:
    """Mark all your notifications as read. Cannot be undone. Requires confirm=true.

    Args:
        confirm: Must be true to execute
    """
    summary = "mark all notifications as read"
    if not (confirm or approval_.confirm):
        return result(NOT_CONFIRMED + summary, _preview(summary))
    user_id = await api.current_user_id()
    await call("core_message_mark_all_notifications_as_read", useridto=user_id)
    await asyncio.to_thread(cache.clear, "notifications")
    out = WriteResult(executed=True, detail="All notifications marked read.")
    return result(out.detail, out)


@mcp.tool(title="Mark activity complete", annotations=SAFE_WRITE)
async def mark_activity_complete(cmid: int, completed: bool = True) -> WriteResult:
    """Manually tick or untick an activity's completion box.

    Args:
        cmid: Course module id
        completed: True to mark complete, false to clear
    """
    await call(
        "core_completion_update_activity_completion_status_manually", cmid=cmid, completed=completed
    )
    await asyncio.to_thread(cache.clear, "activities_completion")
    out = WriteResult(
        executed=True,
        detail=f"Activity {cmid} marked {'complete' if completed else 'incomplete'}.",
        ids={"cmid": cmid},
    )
    return result(out.detail, out)


@mcp.tool(title="Create calendar event", annotations=SAFE_WRITE)
async def create_calendar_event(
    name: str, start: str, duration_minutes: int = 0, description: str = ""
) -> WriteResult:
    """Create a personal calendar event visible only to you.

    Args:
        name: Event title
        start: ISO 8601 start time, e.g. 2026-10-01T09:00:00+04:00
        duration_minutes: Duration, 0 for a point event
        description: Optional description
    """
    data = await call(
        "core_calendar_create_calendar_events",
        events=[
            {
                "name": name,
                "timestart": _ts(start),
                "timeduration": duration_minutes * 60,
                "description": description,
                "eventtype": "user",
            }
        ],
    )
    created = (data.get("events") or [{}])[0]
    await asyncio.to_thread(cache.clear, "calendar_")
    out = WriteResult(
        executed=True,
        detail=f"Created event '{name}'.",
        ids={"event_id": int(created.get("id") or 0)},
    )
    return result(out.detail, out)
