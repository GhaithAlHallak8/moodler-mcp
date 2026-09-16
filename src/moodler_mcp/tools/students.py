from mcp.types import ToolAnnotations
from pydantic import BaseModel

from moodler_mcp import moodle_api as api
from moodler_mcp.results import iso, result
from moodler_mcp.server import mcp

READ = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)


class User(BaseModel):
    user_id: int
    fullname: str
    email: str | None
    department: str | None
    roles: list[str]
    groups: list[str]
    last_access: str | None


class UserList(BaseModel):
    course_id: int
    total: int
    users: list[User]


def _user(u: dict) -> User:
    return User(
        user_id=u["id"],
        fullname=u.get("fullname", ""),
        email=u.get("email"),
        department=u.get("department"),
        roles=[r.get("shortname") or r.get("name", "") for r in u.get("roles", [])],
        groups=[g.get("name", "") for g in u.get("groups", [])],
        last_access=iso(u.get("lastcourseaccess") or u.get("lastaccess")),
    )


@mcp.tool(title="Search students", annotations=READ)
async def search_students(course_id: int, query: str = "") -> UserList:
    """Teacher view: search enrolled users in a course by name or email.

    Args:
        course_id: The Moodle course id
        query: Name or email fragment; empty returns the first 50 users
    """
    users = [_user(u) for u in await api.search_users(course_id=course_id, query=query)]
    return result(
        f"{len(users)} user(s) matching '{query}'.",
        UserList(course_id=course_id, total=len(users), users=users),
    )


@mcp.tool(title="Course roster", annotations=READ)
async def get_course_roster(course_id: int) -> UserList:
    """Teacher view: every enrolled user in a course with roles and groups.

    Args:
        course_id: The Moodle course id
    """
    users = [_user(u) for u in await api.enrolled_users(course_id=course_id)]
    return result(
        f"{len(users)} enrolled user(s).",
        UserList(course_id=course_id, total=len(users), users=users),
    )
