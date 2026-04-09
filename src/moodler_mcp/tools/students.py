import json

from moodler_mcp.moodle_api import search_course_users
from moodler_mcp.server import mcp


@mcp.tool()
async def search_students(course_id: int, query: str = "") -> str:
    """Search for students enrolled in a course.

    Args:
        course_id: The Moodle course ID
        query: Search query (name or email). Empty string returns all.
    """
    data = await search_course_users(
        course_id=course_id,
        query=query,
    )
    users = []
    for u in data.get("users", []):
        users.append(
            {
                "id": u.get("id"),
                "fullname": u.get("fullname", ""),
                "email": u.get("email", ""),
                "profileimageurl": u.get("profileimageurl", ""),
            }
        )
    return json.dumps({"total": len(users), "students": users}, indent=2)
