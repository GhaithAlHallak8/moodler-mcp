import asyncio
from datetime import datetime

from mcp.types import ToolAnnotations
from pydantic import BaseModel

from moodler_mcp import cache
from moodler_mcp.client import call
from moodler_mcp.results import result
from moodler_mcp.server import mcp

WRITE = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=False
)
NOT_CONFIRMED = "Not executed. Call again with confirm=true to proceed: "


class WriteResult(BaseModel):
    executed: bool
    detail: str


@mcp.tool(title="Save assignment grade", annotations=WRITE)
async def save_assignment_grade(
    assign_id: int, user_id: int, grade: float, feedback: str = "", confirm: bool = False
) -> WriteResult:
    """Teacher: record a grade and optional feedback comment for one student. Requires confirm=true.

    Args:
        assign_id: Assignment instance id
        user_id: Student user id
        grade: Numeric grade on the assignment's scale
        feedback: Feedback comment, plain text or HTML
        confirm: Must be true to execute
    """
    summary = f"grade user {user_id} on assignment {assign_id} with {grade}"
    if not confirm:
        return result(NOT_CONFIRMED + summary, WriteResult(executed=False, detail=summary))
    await call(
        "mod_assign_save_grade",
        assignmentid=assign_id,
        userid=user_id,
        grade=grade,
        attemptnumber=-1,
        addattempt=False,
        workflowstate="",
        applytoall=False,
        plugindata={"assignfeedbackcomments_editor": {"text": feedback, "format": 1}},
    )
    await asyncio.to_thread(cache.clear, f'"assign_id": {assign_id}')
    out = WriteResult(executed=True, detail=f"Saved grade {grade} for user {user_id}.")
    return result(out.detail, out)


@mcp.tool(title="Grant extension", annotations=WRITE)
async def grant_extension(
    assign_id: int, user_id: int, until: str, confirm: bool = False
) -> WriteResult:
    """Teacher: grant a due-date extension to one student. Requires confirm=true.

    Args:
        assign_id: Assignment instance id
        user_id: Student user id
        until: New deadline as ISO 8601, e.g. 2026-10-05T23:59:00+04:00
        confirm: Must be true to execute
    """
    ts = int(datetime.fromisoformat(until).timestamp())
    summary = f"extend assignment {assign_id} for user {user_id} until {until}"
    if not confirm:
        return result(NOT_CONFIRMED + summary, WriteResult(executed=False, detail=summary))
    await call(
        "mod_assign_save_user_extensions", assignmentid=assign_id, userids=[user_id], dates=[ts]
    )
    await asyncio.to_thread(cache.clear, f'"assign_id": {assign_id}')
    out = WriteResult(executed=True, detail=f"Extension granted until {until}.")
    return result(out.detail, out)
