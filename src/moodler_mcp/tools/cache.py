import asyncio

from mcp.types import ToolAnnotations

from moodler_mcp import cache
from moodler_mcp.server import mcp


@mcp.tool(
    title="Clear cache",
    annotations=ToolAnnotations(
        read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False
    ),
)
async def clear_cache(pattern: str | None = None) -> str:
    """Clear cached Moodle data.

    Use this when you know cached data is stale — for example, after a new
    assignment has been posted, grades were just released, or course
    enrollments changed.

    Args:
        pattern: Optional substring to match against cache keys. Cache keys
            are of the form `v2:<wrapper_name>:<args_json>`, so passing
            e.g. `"grades_table"` clears only grade reports, and
            `"course_contents"` clears only course contents. Omit to
            clear the entire cache.
    """
    count = await asyncio.to_thread(cache.clear, pattern)
    scope = f"matching {pattern!r}" if pattern else "(all)"
    return f"Cleared {count} cache entries {scope}."
