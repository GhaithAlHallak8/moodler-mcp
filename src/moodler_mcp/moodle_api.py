from __future__ import annotations

from typing import cast

from moodler_mcp.auth import load_session
from moodler_mcp.cache import cached
from moodler_mcp.client import call


async def current_user_id() -> int:
    return load_session().userid


@cached(ttl=86400)
async def site_info() -> dict:
    return cast(dict, await call("core_webservice_get_site_info"))


@cached(ttl=86400)
async def enrolled_courses(*, classification: str, limit: int) -> dict:
    return cast(
        dict,
        await call(
            "core_course_get_enrolled_courses_by_timeline_classification",
            classification=classification,
            limit=limit,
        ),
    )


@cached(ttl=3600)
async def course_contents(*, course_id: int) -> list:
    return cast(list, await call("core_course_get_contents", courseid=course_id))


@cached(ttl=86400)
async def course_module(*, cmid: int) -> dict:
    return cast(dict, await call("core_course_get_course_module", cmid=cmid))


@cached(ttl=1800)
async def events_by_course(*, course_id: int, timesortfrom: int) -> dict:
    return cast(
        dict,
        await call(
            "core_calendar_get_action_events_by_course",
            courseid=course_id,
            timesortfrom=timesortfrom,
        ),
    )


@cached(ttl=1800)
async def events_by_timesort(*, timesortfrom: int, limitnum: int) -> dict:
    return cast(
        dict,
        await call(
            "core_calendar_get_action_events_by_timesort",
            timesortfrom=timesortfrom,
            limitnum=limitnum,
        ),
    )


@cached(ttl=1800)
async def calendar_month(*, year: int, month: int) -> dict:
    return cast(dict, await call("core_calendar_get_calendar_monthly_view", year=year, month=month))


@cached(ttl=1800)
async def calendar_upcoming(*, course_id: int) -> dict:
    return cast(dict, await call("core_calendar_get_calendar_upcoming_view", courseid=course_id))


@cached(ttl=300)
async def grades_table(*, course_id: int, user_id: int) -> dict:
    return cast(
        dict, await call("gradereport_user_get_grades_table", courseid=course_id, userid=user_id)
    )


@cached(ttl=300)
async def grade_overview() -> dict:
    return cast(dict, await call("gradereport_overview_get_course_grades"))


@cached(ttl=3600)
async def grade_items(*, course_id: int) -> dict:
    return cast(dict, await call("core_grades_get_gradeitems", courseid=course_id))


@cached(ttl=600)
async def assignments(*, course_id: int) -> dict:
    return cast(dict, await call("mod_assign_get_assignments", courseids=[course_id]))


@cached(ttl=600)
async def submission_status(*, assign_id: int) -> dict:
    return cast(dict, await call("mod_assign_get_submission_status", assignid=assign_id))


@cached(ttl=600)
async def assign_submissions(*, assign_id: int) -> dict:
    return cast(dict, await call("mod_assign_get_submissions", assignmentids=[assign_id]))


@cached(ttl=600)
async def assign_grades(*, assign_id: int) -> dict:
    return cast(dict, await call("mod_assign_get_grades", assignmentids=[assign_id]))


@cached(ttl=600)
async def assign_participants(*, assign_id: int, group_id: int) -> dict:
    return cast(
        dict,
        await call("mod_assign_list_participants", assignid=assign_id, groupid=group_id, filter=""),
    )


@cached(ttl=600)
async def assign_participant(*, assign_id: int, user_id: int) -> dict:
    return cast(dict, await call("mod_assign_get_participant", assignid=assign_id, userid=user_id))


@cached(ttl=86400)
async def pages_by_course(*, course_id: int) -> dict:
    return cast(dict, await call("mod_page_get_pages_by_courses", courseids=[course_id]))


@cached(ttl=86400)
async def urls_by_course(*, course_id: int) -> dict:
    return cast(dict, await call("mod_url_get_urls_by_courses", courseids=[course_id]))


@cached(ttl=86400)
async def folders_by_course(*, course_id: int) -> dict:
    return cast(dict, await call("mod_folder_get_folders_by_courses", courseids=[course_id]))


@cached(ttl=86400)
async def resources_by_course(*, course_id: int) -> dict:
    return cast(dict, await call("mod_resource_get_resources_by_courses", courseids=[course_id]))


@cached(ttl=900)
async def search_users(*, course_id: int, query: str, perpage: int = 50) -> list:
    return cast(
        list,
        await call(
            "core_enrol_search_users",
            courseid=course_id,
            search=query,
            searchanywhere=True,
            page=0,
            perpage=perpage,
        ),
    )


@cached(ttl=900)
async def enrolled_users(*, course_id: int) -> list:
    return cast(
        list,
        await call(
            "core_enrol_get_enrolled_users",
            courseid=course_id,
            options=[
                {
                    "name": "userfields",
                    "value": "id,fullname,email,roles,groups,lastcourseaccess,department",
                }
            ],
        ),
    )


@cached(ttl=60)
async def notifications(*, limit: int, offset: int) -> dict:
    return cast(
        dict,
        await call(
            "message_popup_get_popup_notifications",
            useridto=0,
            newestfirst=True,
            limit=limit,
            offset=offset,
        ),
    )


@cached(ttl=60)
async def conversations(*, user_id: int, limit: int) -> dict:
    return cast(
        dict,
        await call("core_message_get_conversations", userid=user_id, limitfrom=0, limitnum=limit),
    )


@cached(ttl=60)
async def conversation_messages(*, user_id: int, conversation_id: int, limit: int) -> dict:
    return cast(
        dict,
        await call(
            "core_message_get_conversation_messages",
            currentuserid=user_id,
            convid=conversation_id,
            limitfrom=0,
            limitnum=limit,
            newest=True,
        ),
    )


@cached(ttl=3600)
async def forums(*, course_id: int) -> list:
    return cast(list, await call("mod_forum_get_forums_by_courses", courseids=[course_id]))


@cached(ttl=300)
async def discussions(*, forum_id: int, page: int, perpage: int) -> dict:
    return cast(
        dict,
        await call("mod_forum_get_forum_discussions", forumid=forum_id, page=page, perpage=perpage),
    )


@cached(ttl=300)
async def discussion_posts(*, discussion_id: int) -> dict:
    return cast(
        dict,
        await call(
            "mod_forum_get_discussion_posts",
            discussionid=discussion_id,
            sortby="created",
            sortdirection="ASC",
        ),
    )


@cached(ttl=3600)
async def quizzes(*, course_id: int) -> dict:
    return cast(dict, await call("mod_quiz_get_quizzes_by_courses", courseids=[course_id]))


@cached(ttl=300)
async def quiz_attempts(*, quiz_id: int) -> dict:
    return cast(dict, await call("mod_quiz_get_user_attempts", quizid=quiz_id, status="all"))


@cached(ttl=300)
async def quiz_best_grade(*, quiz_id: int) -> dict:
    return cast(dict, await call("mod_quiz_get_user_best_grade", quizid=quiz_id))


@cached(ttl=3600)
async def attempt_review(*, attempt_id: int) -> dict:
    return cast(dict, await call("mod_quiz_get_attempt_review", attemptid=attempt_id))


@cached(ttl=300)
async def activities_completion(*, course_id: int, user_id: int) -> dict:
    return cast(
        dict,
        await call(
            "core_completion_get_activities_completion_status", courseid=course_id, userid=user_id
        ),
    )


@cached(ttl=300)
async def course_completion(*, course_id: int, user_id: int) -> dict:
    return cast(
        dict,
        await call(
            "core_completion_get_course_completion_status", courseid=course_id, userid=user_id
        ),
    )
