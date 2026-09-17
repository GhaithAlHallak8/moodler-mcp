import base64
import mimetypes
import os
from pathlib import Path
from urllib.parse import quote

from mcp.server.caching import CacheHint
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.resources import FunctionResource
from mcp.types import Icon

from moodler_mcp.config import DOWNLOADS_DIR

INSTRUCTIONS = """moodler-mcp talks to one Moodle site as the signed-in user.

Sign-in: if any tool reports you are not signed in, call login_to_moodle once; it opens a browser for SSO and stores a token. Never call it otherwise.

Finding things: list_courses gives course ids; get_course_contents gives every module with its cmid and direct file URLs; list_assignments gives assignment ids (assign_id) and cmids.

Files: call download_resource with a pluginfile URL, or with a /mod/resource or /mod/folder URL. It returns the content, the absolute local path, and on local clients the file itself. Use read_downloaded_file only for paths listed after a zip download. Do not call get_module_content for plain files.

Assignments: get_assignment_feedback takes a cmid; get_grading_summary, get_assignment_participants and submit_assignment take an assign_id.

Writes exist only when the operator enabled MOODLER_ALLOW_STUDENT_WRITES or MOODLER_ALLOW_TEACHER_GRADING. Destructive writes require confirm=true or an explicit approval prompt.
"""

_ICON_PATH = Path(__file__).resolve().parents[2] / "assets" / "icon.png"
_ICON_MAX_BYTES = 64_000


def _icon() -> list[Icon]:
    if not _ICON_PATH.exists() or _ICON_PATH.stat().st_size > _ICON_MAX_BYTES:
        return []
    data = base64.b64encode(_ICON_PATH.read_bytes()).decode()
    return [Icon(src=f"data:image/png;base64,{data}", mime_type="image/png", sizes=["any"])]


mcp = MCPServer(
    "moodler-mcp",
    title="Moodler MCP",
    instructions=INSTRUCTIONS,
    icons=_icon(),
    warn_on_duplicate_resources=False,
    cache_hints={
        "tools/list": CacheHint(ttl_ms=3_600_000),
        "prompts/list": CacheHint(ttl_ms=3_600_000),
        "resources/list": CacheHint(ttl_ms=60_000),
        "resources/read": CacheHint(ttl_ms=86_400_000),
    },
)


def download_uri(filename: str) -> str:
    return f"downloads://{quote(filename)}"


def register_download(path: str) -> str:
    filename = os.path.basename(path)
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    file_path = Path(path)

    def read() -> bytes:
        return file_path.read_bytes()

    uri = download_uri(filename)
    mcp.add_resource(
        FunctionResource(uri=uri, name=filename, title=filename, mime_type=mime, fn=read)
    )
    return uri


def _register_existing_downloads() -> None:
    if not os.path.isdir(DOWNLOADS_DIR):
        return
    for name in sorted(os.listdir(DOWNLOADS_DIR)):
        full = os.path.join(DOWNLOADS_DIR, name)
        if os.path.isfile(full) and not name.startswith("."):
            register_download(full)


_register_existing_downloads()

import moodler_mcp.prompts  # noqa: F401, E402
import moodler_mcp.tools.assignments  # noqa: F401, E402
import moodler_mcp.tools.auth  # noqa: F401, E402
import moodler_mcp.tools.cache  # noqa: F401, E402
import moodler_mcp.tools.calendar  # noqa: F401, E402
import moodler_mcp.tools.courses  # noqa: F401, E402
import moodler_mcp.tools.forums  # noqa: F401, E402
import moodler_mcp.tools.grades  # noqa: F401, E402
import moodler_mcp.tools.messaging  # noqa: F401, E402
import moodler_mcp.tools.quizzes  # noqa: F401, E402
import moodler_mcp.tools.students  # noqa: F401, E402
from moodler_mcp.config import ALLOW_STUDENT_WRITES, ALLOW_TEACHER_GRADING  # noqa: E402

if ALLOW_STUDENT_WRITES:
    import moodler_mcp.tools.writes_student  # noqa: F401
if ALLOW_TEACHER_GRADING:
    import moodler_mcp.tools.writes_teacher  # noqa: F401
