from mcp.types import ToolAnnotations
from pydantic import BaseModel

from moodler_mcp import moodle_api as api
from moodler_mcp.client import MoodleError
from moodler_mcp.results import iso, result, strip_html
from moodler_mcp.server import mcp

READ = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)


class CalendarEvent(BaseModel):
    id: int
    name: str
    eventtype: str
    course: str | None
    modname: str | None
    start: str | None
    duration_s: int
    url: str | None
    description: str


class CalendarView(BaseModel):
    scope: str
    total: int
    events: list[CalendarEvent]


class ActivityCompletion(BaseModel):
    cmid: int
    modname: str
    state: int
    completed_at: str | None
    tracking: int


class CompletionStatus(BaseModel):
    course_id: int
    course_completed: bool | None
    completed: int
    total: int
    activities: list[ActivityCompletion]


def _event(e: dict) -> CalendarEvent:
    course = e.get("course") or {}
    return CalendarEvent(
        id=e["id"],
        name=e.get("name", ""),
        eventtype=e.get("eventtype", ""),
        course=course.get("fullname"),
        modname=e.get("modulename"),
        start=iso(e.get("timestart")),
        duration_s=int(e.get("timeduration") or 0),
        url=e.get("url"),
        description=strip_html(e.get("description"))[:500],
    )


@mcp.tool(title="Calendar month", annotations=READ)
async def get_calendar(year: int, month: int) -> CalendarView:
    """Every calendar event in a month across your courses, including non-deadline
    events such as lectures and exams.

    Args:
        year: Four-digit year
        month: 1 to 12
    """
    data = await api.calendar_month(year=year, month=month)
    events = [
        _event(e)
        for w in data.get("weeks", [])
        for d in w.get("days", [])
        for e in d.get("events", [])
    ]
    return result(
        f"{len(events)} event(s) in {year}-{month:02d}.",
        CalendarView(scope=f"{year}-{month:02d}", total=len(events), events=events),
    )


@mcp.tool(title="Calendar upcoming", annotations=READ)
async def get_calendar_upcoming(course_id: int = 1) -> CalendarView:
    """Upcoming calendar events, optionally for one course (course_id 1 means all).

    Args:
        course_id: The Moodle course id, or 1 for all courses
    """
    data = await api.calendar_upcoming(course_id=course_id)
    events = [_event(e) for e in data.get("events", [])]
    return result(
        f"{len(events)} upcoming event(s).",
        CalendarView(scope="upcoming", total=len(events), events=events),
    )


@mcp.tool(title="Completion status", annotations=READ)
async def get_completion_status(course_id: int) -> CompletionStatus:
    """Which activities you have completed in a course, and whether the course is complete.

    Args:
        course_id: The Moodle course id
    """
    user_id = await api.current_user_id()
    acts = await api.activities_completion(course_id=course_id, user_id=user_id)
    activities = [
        ActivityCompletion(
            cmid=s["cmid"],
            modname=s.get("modname", ""),
            state=int(s.get("state") or 0),
            completed_at=iso(s.get("timecompleted")),
            tracking=int(s.get("tracking") or 0),
        )
        for s in acts.get("statuses", [])
    ]
    course_completed: bool | None
    try:
        course = await api.course_completion(course_id=course_id, user_id=user_id)
        course_completed = bool((course.get("completionstatus") or {}).get("completed"))
    except MoodleError:
        course_completed = None
    done = sum(1 for a in activities if a.state in (1, 2))
    return result(
        f"{done}/{len(activities)} activities complete.",
        CompletionStatus(
            course_id=course_id,
            course_completed=course_completed,
            completed=done,
            total=len(activities),
            activities=activities,
        ),
    )
