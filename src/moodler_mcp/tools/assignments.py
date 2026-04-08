import json
import time
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from moodler_mcp.client import call_moodle, fetch_page
from moodler_mcp.server import mcp


@mcp.tool()
async def get_course_deadlines(course_id: int, include_past: bool = True) -> str:
    """Get all assignments, quizzes, and deadlines for a course.

    Returns calendar action events (assignments due, quiz deadlines, etc.)

    Args:
        course_id: The Moodle course ID
        include_past: If True, include past deadlines. If False, only future.
    """
    timefrom = 1 if include_past else int(time.time())
    data = await call_moodle(
        "core_calendar_get_action_events_by_course",
        courseid=course_id,
        timesortfrom=timefrom,
    )
    events = []
    for e in data.get("events", []):
        event = {
            "id": e.get("id"),
            "name": e.get("name", ""),
            "type": e.get("modulename", ""),
            "instance_id": e.get("instance"),
            "course_id": e.get("course", {}).get("id") if isinstance(e.get("course"), dict) else e.get("courseid"),
        }
        if e.get("timestart"):
            event["due_date"] = datetime.fromtimestamp(
                e["timestart"], tz=timezone.utc
            ).isoformat()
        if e.get("url"):
            event["url"] = e["url"]
        events.append(event)
    return json.dumps({"total": len(events), "events": events}, indent=2)


@mcp.tool()
async def get_upcoming_deadlines(limit: int = 20) -> str:
    """Get upcoming deadlines across all courses, sorted by date.

    Args:
        limit: Max number of events (max 50)
    """
    limit = min(limit, 50)
    data = await call_moodle(
        "core_calendar_get_action_events_by_timesort",
        timesortfrom=int(time.time()),
        limitnum=limit,
    )
    events = []
    for e in data.get("events", []):
        event = {
            "name": e.get("name", ""),
            "type": e.get("modulename", ""),
            "course": e.get("course", {}).get("fullname", "") if isinstance(e.get("course"), dict) else "",
        }
        if e.get("timestart"):
            event["due_date"] = datetime.fromtimestamp(
                e["timestart"], tz=timezone.utc
            ).isoformat()
        if e.get("url"):
            event["url"] = e["url"]
        events.append(event)
    return json.dumps({"total": len(events), "events": events}, indent=2)


@mcp.tool()
async def get_assignment_participants(
    assign_id: int,
    group_id: int = 0,
    filter_text: str = "",
) -> str:
    """List participants for a specific assignment with submission status.

    Args:
        assign_id: The assignment instance ID (from get_course_deadlines)
        group_id: Group ID to filter by (0 for all)
        filter_text: Filter participants by name
    """
    data = await call_moodle(
        "mod_assign_list_participants",
        assignid=assign_id,
        groupid=group_id,
        filter=filter_text,
    )
    participants = []
    if isinstance(data, list):
        for p in data:
            participants.append({
                "id": p.get("id"),
                "fullname": p.get("fullname", ""),
                "submitted": p.get("submitted", False),
                "requiregrading": p.get("requiregrading", False),
                "groupname": p.get("groupname", ""),
            })
    return json.dumps(
        {"total": len(participants), "participants": participants}, indent=2
    )


@mcp.tool()
async def get_assignment_participant_detail(
    assign_id: int, user_id: int
) -> str:
    """Get detailed submission info for a student on a specific assignment.

    Args:
        assign_id: The assignment instance ID
        user_id: The student's user ID
    """
    data = await call_moodle(
        "mod_assign_get_participant",
        assignid=assign_id,
        userid=user_id,
    )
    return json.dumps(data, indent=2)


def _extract_plugin_content(plugins: list) -> dict:
    """Extract text and file URLs from assign submission/feedback plugins."""
    out: dict = {}
    for plugin in plugins or []:
        ptype = plugin.get("type", "")
        for editor in plugin.get("editorfields", []) or []:
            text = (editor.get("text") or "").strip()
            if text:
                key = f"{ptype}_{editor.get('name', 'text')}"
                out[key] = text

        files: list[dict] = []
        for area in plugin.get("fileareas", []) or []:
            for f in area.get("files", []) or []:
                files.append({
                    "filename": f.get("filename", ""),
                    "url": f.get("fileurl", ""),
                    "size": f.get("filesize"),
                    "mimetype": f.get("mimetype", ""),
                })
        if files:
            out[f"{ptype}_files"] = files
    return out


@mcp.tool()
async def get_assignment_feedback(cmid: int) -> str:
    """Get your submission status, grade, and feedback for an assignment.

    Use the `id` from a /mod/assign/view.php?id=... URL as the cmid.
    Returns submission status, submitted text/files, grade, and grader
    feedback (comments + annotated files).

    Args:
        cmid: The course module id (the `id` in the assignment view URL)
    """
    cm = await call_moodle("core_course_get_course_module", cmid=cmid)
    cm_info = cm.get("cm", {}) if isinstance(cm, dict) else {}
    assign_id = cm_info.get("instance")
    course_id = cm_info.get("course")
    assign_name = cm_info.get("name", "")
    if not assign_id:
        return json.dumps(
            {"error": "Could not resolve cmid to an assignment instance", "raw": cm},
            indent=2,
        )

    result: dict = {
        "cmid": cmid,
        "assign_id": assign_id,
        "course_id": course_id,
        "name": assign_name,
    }

    try:
        status = await call_moodle(
            "mod_assign_get_submission_status", assignid=assign_id
        )
        last = status.get("lastattempt", {}) or {}
        submission = last.get("submission", {}) or {}
        feedback = status.get("feedback", {}) or {}
        gradefordisplay = feedback.get("gradefordisplay", "")

        result["submission"] = {
            "status": submission.get("status", ""),
            "gradingstatus": last.get("gradingstatus", ""),
            "timemodified": submission.get("timemodified"),
            "submitted_at": submission.get("timecreated"),
            "content": _extract_plugin_content(submission.get("plugins", [])),
        }
        result["feedback"] = {
            "grade": (feedback.get("grade") or {}).get("grade"),
            "grade_display": gradefordisplay,
            "graded_at": (feedback.get("grade") or {}).get("timemodified"),
            "content": _extract_plugin_content(feedback.get("plugins", [])),
        }
        # Strip the HTML wrapper Moodle adds around gradefordisplay if present
        if gradefordisplay:
            result["feedback"]["grade_display_text"] = BeautifulSoup(
                gradefordisplay, "html.parser"
            ).get_text(" ", strip=True)
        return json.dumps(result, indent=2)
    except RuntimeError as e:
        result["web_service_error"] = str(e)

    try:
        html = await fetch_page(f"/mod/assign/view.php?id={cmid}")
        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one("table.generaltable") or soup.select_one(
            ".submissionstatustable"
        )
        if table:
            rows = {}
            for tr in table.select("tr"):
                th = tr.select_one("th")
                td = tr.select_one("td")
                if th and td:
                    rows[th.get_text(" ", strip=True)] = td.get_text(" ", strip=True)
            result["scraped"] = rows
        else:
            result["scraped_html"] = str(soup.select_one("#region-main") or soup.body)
    except Exception as e:
        result["scrape_error"] = f"{type(e).__name__}: {e}"

    return json.dumps(result, indent=2)
