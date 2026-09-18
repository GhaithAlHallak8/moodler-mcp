import asyncio
import time

from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from moodler_mcp import moodle_api as api
from moodler_mcp.results import iso, result, strip_html
from moodler_mcp.server import mcp

READ = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)


class Event(BaseModel):
    id: int
    name: str
    course_id: int | None
    course: str | None
    modname: str | None
    due: str | None
    overdue: bool
    action: str | None
    url: str | None


class EventList(BaseModel):
    total: int
    events: list[Event]


class Attachment(BaseModel):
    filename: str
    url: str
    size: int


class Feedback(BaseModel):
    assign_id: int
    status: str | None
    submitted_at: str | None
    grading_status: str | None
    grade: str | None
    graded_at: str | None
    grader_id: int | None
    comments: str
    feedback_files: list[Attachment]
    submission_files: list[Attachment]
    submission_text: str


class GradingSummary(BaseModel):
    assign_id: int
    participants: int
    submitted: int
    drafts: int
    needs_grading: int
    graded: int


class GradingRow(BaseModel):
    user_id: int
    fullname: str
    email: str | None
    status: str | None
    submitted_at: str | None
    grading_status: str | None
    grade: str | None
    graded_at: str | None
    extension_until: str | None


class GradingTable(BaseModel):
    assign_id: int
    cmid: int
    rows: list[GradingRow]


class Participant(BaseModel):
    user_id: int
    fullname: str
    email: str | None
    submitted: bool
    requires_grading: bool
    granted_extension: bool
    group: str | None


class ParticipantList(BaseModel):
    assign_id: int
    total: int
    participants: list[Participant]


class ParticipantDetail(BaseModel):
    assign_id: int
    user_id: int
    fullname: str
    email: str | None
    submitted: bool
    requires_grading: bool
    granted_extension: bool
    due: str | None
    cutoff: str | None
    status: str | None
    submitted_at: str | None
    grading_status: str | None


def _event(e: dict) -> Event:
    course = e.get("course") or {}
    action = e.get("action") or {}
    return Event(
        id=e["id"],
        name=e.get("activityname") or e.get("name", ""),
        course_id=course.get("id"),
        course=course.get("fullname"),
        modname=e.get("modulename"),
        due=iso(e.get("timesort") or e.get("timestart")),
        overdue=bool(e.get("overdue")),
        action=action.get("name"),
        url=e.get("url"),
    )


def _attachments(areas: list[dict]) -> list[Attachment]:
    out: list[Attachment] = []
    for area in areas:
        for f in area.get("files", []):
            out.append(
                Attachment(
                    filename=f.get("filename", ""),
                    url=f.get("fileurl", ""),
                    size=int(f.get("filesize") or 0),
                )
            )
    return out


def _quarter_hour() -> int:
    return int(time.time()) // 900 * 900


def _editor_text(plugins: list[dict]) -> str:
    parts = []
    for p in plugins:
        for field in p.get("editorfields", []):
            parts.append(strip_html(field.get("text")))
    return "\n".join(t for t in parts if t)


@mcp.tool(title="Course deadlines", annotations=READ)
async def get_course_deadlines(course_id: int, include_past: bool = True) -> EventList:
    """Assignment, quiz and other action deadlines for one course.

    Args:
        course_id: The Moodle course id
        include_past: Include deadlines already passed
    """
    since = 0 if include_past else _quarter_hour()
    data = await api.events_by_course(course_id=course_id, timesortfrom=since)
    events = [_event(e) for e in data.get("events", [])]
    return result(
        f"{len(events)} deadline(s) for course {course_id}.",
        EventList(total=len(events), events=events),
    )


@mcp.tool(title="Upcoming deadlines", annotations=READ)
async def get_upcoming_deadlines(limit: int = 20) -> EventList:
    """Upcoming deadlines across all your courses, soonest first.

    Args:
        limit: Max number of events (max 50)
    """
    data = await api.events_by_timesort(timesortfrom=_quarter_hour(), limitnum=min(limit, 50))
    events = [_event(e) for e in data.get("events", [])]
    return result(
        f"{len(events)} upcoming deadline(s).", EventList(total=len(events), events=events)
    )


async def _assign_id(cmid: int) -> int:
    cm = (await api.course_module(cmid=cmid))["cm"]
    if cm.get("modname") != "assign":
        raise ToolError(f"cmid {cmid} is a {cm.get('modname')}, not an assignment")
    return int(cm["instance"])


@mcp.tool(title="Assignment feedback", annotations=READ)
async def get_assignment_feedback(cmid: int) -> Feedback:
    """Your submission status, grade and teacher feedback for one assignment.

    Args:
        cmid: Course module id of the assignment (from get_course_contents)
    """
    assign_id = await _assign_id(cmid)
    data = await api.submission_status(assign_id=assign_id)
    last = data.get("lastattempt") or {}
    sub = last.get("submission") or {}
    fb = data.get("feedback") or {}
    grade = fb.get("grade") or {}
    feedback_plugins = fb.get("plugins", [])
    display = fb.get("gradefordisplay")
    out = Feedback(
        assign_id=assign_id,
        status=sub.get("status"),
        submitted_at=iso(sub.get("timemodified")),
        grading_status=last.get("gradingstatus"),
        grade=strip_html(display) if display else None,
        graded_at=iso(fb.get("gradeddate")),
        grader_id=grade.get("grader"),
        comments=_editor_text(feedback_plugins),
        feedback_files=_attachments([a for p in feedback_plugins for a in p.get("fileareas", [])]),
        submission_files=_attachments(
            [a for p in sub.get("plugins", []) for a in p.get("fileareas", [])]
        ),
        submission_text=_editor_text(sub.get("plugins", [])),
    )
    return result(f"Status {out.status or 'none'}, grade {out.grade or 'not graded'}.", out)


@mcp.tool(title="Grading summary", annotations=READ)
async def get_grading_summary(assign_id: int) -> GradingSummary:
    """Teacher view: submission and grading counts for an assignment.

    Args:
        assign_id: Assignment instance id (module 'instance' from get_course_contents)
    """
    status = (await api.submission_status(assign_id=assign_id)).get("gradingsummary") or {}
    grades = await api.assign_grades(assign_id=assign_id)
    graded = sum(len(a.get("grades", [])) for a in grades.get("assignments", []))
    out = GradingSummary(
        assign_id=assign_id,
        participants=int(status.get("participantcount") or 0),
        submitted=int(status.get("submissionssubmittedcount") or 0),
        drafts=int(status.get("submissiondraftscount") or 0),
        needs_grading=int(status.get("submissionsneedgradingcount") or 0),
        graded=graded,
    )
    return result(
        f"{out.submitted}/{out.participants} submitted, {out.needs_grading} need grading.", out
    )


@mcp.tool(title="Grading table", annotations=READ)
async def get_grading_table(cmid: int) -> GradingTable:
    """Teacher view: one row per participant with submission status and grade.

    Args:
        cmid: Course module id of the assignment
    """
    assign_id = await _assign_id(cmid)
    part_data, sub_data, grade_data = await asyncio.gather(
        api.assign_participants(assign_id=assign_id, group_id=0),
        api.assign_submissions(assign_id=assign_id),
        api.assign_grades(assign_id=assign_id),
    )
    participants = part_data.get("participants", [])
    subs = {
        s["userid"]: s for a in sub_data.get("assignments", []) for s in a.get("submissions", [])
    }
    grades = {
        g["userid"]: g for a in grade_data.get("assignments", []) for g in a.get("grades", [])
    }
    rows = []
    for p in participants:
        s = subs.get(p["id"], {})
        g = grades.get(p["id"], {})
        rows.append(
            GradingRow(
                user_id=p["id"],
                fullname=p.get("fullname", ""),
                email=p.get("email"),
                status=s.get("status") or p.get("submissionstatus"),
                submitted_at=iso(s.get("timemodified")),
                grading_status=s.get("gradingstatus"),
                grade=g.get("grade"),
                graded_at=iso(g.get("timemodified")),
                extension_until=iso(p.get("extensionduedate")),
            )
        )
    return result(
        f"{len(rows)} participant(s).", GradingTable(assign_id=assign_id, cmid=cmid, rows=rows)
    )


@mcp.tool(title="Assignment participants", annotations=READ)
async def get_assignment_participants(
    assign_id: int, group_id: int = 0, filter: str = ""
) -> ParticipantList:
    """Teacher view: participants of an assignment with submission flags.

    Args:
        assign_id: Assignment instance id
        group_id: Restrict to a group (0 for all)
        filter: Case-insensitive substring on name or email
    """
    data = (await api.assign_participants(assign_id=assign_id, group_id=group_id)).get(
        "participants", []
    )
    needle = filter.lower()
    rows = [
        Participant(
            user_id=p["id"],
            fullname=p.get("fullname", ""),
            email=p.get("email"),
            submitted=bool(p.get("submitted")),
            requires_grading=bool(p.get("requiregrading")),
            granted_extension=bool(p.get("grantedextension")),
            group=p.get("groupname"),
        )
        for p in data
        if not needle or needle in (p.get("fullname", "") + " " + (p.get("email") or "")).lower()
    ]
    return result(
        f"{len(rows)} participant(s).",
        ParticipantList(assign_id=assign_id, total=len(rows), participants=rows),
    )


@mcp.tool(title="Participant detail", annotations=READ)
async def get_assignment_participant_detail(assign_id: int, user_id: int) -> ParticipantDetail:
    """Teacher view: one participant's submission details for an assignment.

    Args:
        assign_id: Assignment instance id
        user_id: The student's user id
    """
    p = (await api.assign_participant(assign_id=assign_id, user_id=user_id)).get(
        "participant"
    ) or {}
    sub = p.get("submission") or {}
    out = ParticipantDetail(
        assign_id=assign_id,
        user_id=user_id,
        fullname=p.get("fullname", ""),
        email=(p.get("user") or {}).get("email"),
        submitted=bool(p.get("submitted")),
        requires_grading=bool(p.get("requiregrading")),
        granted_extension=bool(p.get("grantedextension")),
        due=iso(p.get("duedate")),
        cutoff=iso(p.get("cutoffdate")),
        status=sub.get("status") or p.get("submissionstatus"),
        submitted_at=iso(sub.get("timemodified")),
        grading_status=sub.get("gradingstatus"),
    )
    return result(f"{out.fullname}: {'submitted' if out.submitted else 'not submitted'}.", out)


class Assignment(BaseModel):
    assign_id: int
    cmid: int
    name: str
    due: str | None
    cutoff: str | None
    opens: str | None
    max_grade: float | None
    intro: str
    attachments: list[Attachment]


class AssignmentList(BaseModel):
    course_id: int
    total: int
    assignments: list[Assignment]


@mcp.tool(title="List assignments", annotations=READ)
async def list_assignments(course_id: int) -> AssignmentList:
    """All assignments in a course with due dates, brief and attached files.

    Args:
        course_id: The Moodle course id
    """
    data = await api.assignments(course_id=course_id)
    items = [
        Assignment(
            assign_id=a["id"],
            cmid=a["cmid"],
            name=a.get("name", ""),
            due=iso(a.get("duedate")),
            cutoff=iso(a.get("cutoffdate")),
            opens=iso(a.get("allowsubmissionsfromdate")),
            max_grade=a.get("grade") if (a.get("grade") or 0) > 0 else None,
            intro=strip_html(a.get("intro")),
            attachments=[
                Attachment(
                    filename=f.get("filename", ""),
                    url=f.get("fileurl", ""),
                    size=int(f.get("filesize") or 0),
                )
                for f in a.get("introattachments", [])
            ],
        )
        for course in data.get("courses", [])
        for a in course.get("assignments", [])
    ]
    items.sort(key=lambda a: a.due or "9")
    return result(
        f"{len(items)} assignment(s).",
        AssignmentList(course_id=course_id, total=len(items), assignments=items),
    )
