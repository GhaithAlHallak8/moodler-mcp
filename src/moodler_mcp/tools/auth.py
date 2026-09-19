from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from moodler_mcp.auth import bootstrap
from moodler_mcp.results import result
from moodler_mcp.server import mcp


class LoginResult(BaseModel):
    username: str
    userid: int
    site_release: str


@mcp.tool(
    title="Sign in to Moodle",
    annotations=ToolAnnotations(
        read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False
    ),
)
async def login_to_moodle(ctx: Context) -> LoginResult:
    """Sign in to Moodle once. Opens a browser window for single sign-on, then stores a
    web service token locally so every other tool works without a browser.

    Call this only when another tool reports that you are not signed in, or when the
    user asks to sign in again. Takes up to three minutes while the user completes SSO.
    """

    async def progress(step: float, message: str) -> None:
        await ctx.report_progress(step, 3, message)

    session = await bootstrap(progress)
    data = LoginResult(
        username=session.username, userid=session.userid, site_release=session.site_release
    )
    return result(f"Signed in as {session.username}.", data)
