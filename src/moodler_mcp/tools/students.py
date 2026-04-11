import json

from moodler_mcp.moodle_api import search_course_users
from moodler_mcp.server import mcp


@mcp.tool()
async def search_students(course_id: int, query: str = "") -> str:
    """Search participants enrolled in a course (students, teachers, TAs).

    Requires the "View participants" capability in the target course, which
    depends on site config and the caller's role — may fail for students.

    Args:
        course_id: The Moodle course ID
        query: Search query (name or email). Empty string returns all.
    """
    data = await search_course_users(course_id=course_id, query=query)
    users = [
        {
            "id": u.get("id"),
            "fullname": u.get("fullname", ""),
            "email": u.get("email", ""),
            "profileimageurl": u.get("profileimageurl", ""),
        }
        for u in data
    ]
    return json.dumps({"total": len(users), "participants": users}, indent=2)
