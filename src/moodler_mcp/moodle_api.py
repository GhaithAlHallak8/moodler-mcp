"""Cached wrappers around Moodle operations.

Each function here is a thin `@cached`-decorated wrapper that calls into
`client.py` or `scraper.py` and caches the raw result. Tool modules should
import from this module instead of calling `client.call_moodle` /
`client.fetch_page` / `scraper.scrape_course_contents` directly, so that
caching applies uniformly.

All wrappers are kwargs-only (enforced by `@cached`). Formatting of the
returned data is the caller's responsibility and is intentionally uncached.
"""

from __future__ import annotations

from typing import cast

from moodler_mcp.cache import cached
from moodler_mcp.client import call_moodle, fetch_page
from moodler_mcp.scraper import scrape_course_contents

# ---- courses ----------------------------------------------------------------


@cached(ttl=86400)  # 1 day
async def list_enrolled_courses(*, classification: str, limit: int) -> dict:
    return await call_moodle(
        "core_course_get_enrolled_courses_by_timeline_classification",
        classification=classification,
        limit=limit,
    )


@cached(ttl=3600)  # 1 hour
async def get_course_sections(*, course_id: int) -> list[dict]:
    return await scrape_course_contents(course_id)


# ---- calendar / deadlines ---------------------------------------------------


@cached(ttl=1800)  # 30 min
async def get_events_by_course(*, course_id: int, timesortfrom: int) -> dict:
    return await call_moodle(
        "core_calendar_get_action_events_by_course",
        courseid=course_id,
        timesortfrom=timesortfrom,
    )


@cached(ttl=1800)  # 30 min
async def get_events_by_timesort(*, timesortfrom: int, limitnum: int) -> dict:
    return await call_moodle(
        "core_calendar_get_action_events_by_timesort",
        timesortfrom=timesortfrom,
        limitnum=limitnum,
    )


# ---- assignments ------------------------------------------------------------


@cached(ttl=600)  # 10 min
async def list_assign_participants(
    *, assign_id: int, group_id: int, filter_text: str
) -> list[dict]:
    return cast(
        list[dict],
        await call_moodle(
            "mod_assign_list_participants",
            assignid=assign_id,
            groupid=group_id,
            filter=filter_text,
        ),
    )


@cached(ttl=600)  # 10 min
async def get_assign_participant(*, assign_id: int, user_id: int) -> dict:
    return await call_moodle(
        "mod_assign_get_participant",
        assignid=assign_id,
        userid=user_id,
    )


@cached(ttl=86400)  # 1 day — module structure is stable
async def get_course_module(*, cmid: int) -> dict:
    return await call_moodle("core_course_get_course_module", cmid=cmid)


@cached(ttl=600)  # 10 min
async def get_assign_submission_status(*, assign_id: int) -> dict:
    return await call_moodle("mod_assign_get_submission_status", assignid=assign_id)


@cached(ttl=600)  # 10 min
async def get_assign_view_html(*, cmid: int) -> str:
    return await fetch_page(f"/mod/assign/view.php?id={cmid}")


@cached(ttl=600)  # 10 min
async def get_assign_grading_html(*, cmid: int) -> str:
    return await fetch_page(
        f"/mod/assign/view.php?id={cmid}&action=grading",
        allow_error_status=True,
    )


# ---- grades -----------------------------------------------------------------


@cached(ttl=300)  # 5 min
async def get_grade_report_html(*, course_id: int) -> str:
    return await fetch_page(f"/grade/report/user/index.php?id={course_id}")


# ---- students ---------------------------------------------------------------


@cached(ttl=900)  # 15 min
async def search_course_users(*, course_id: int, query: str) -> dict:
    return await call_moodle(
        "core_grades_get_enrolled_users_for_search_widget",
        courseid=course_id,
        actionbaseurl="",
        groupid=0,
        search=query,
    )
