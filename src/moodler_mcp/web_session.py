import re

import httpx

from moodler_mcp.auth import load_session
from moodler_mcp.client import MoodleError
from moodler_mcp.config import APP_USER_AGENT, MOODLE_URL, USER_AGENT

_jar: httpx.Cookies | None = None


def _lockout_message(message: str) -> str:
    match = re.search(r"(\d+)\s*min", message)
    wait = f"{match.group(1)} minutes" if match else "a few minutes"
    return f"Moodle allows one web session every 6 minutes; try again in {wait}."


async def _acquire() -> httpx.Cookies:
    session = load_session()
    async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": APP_USER_AGENT}) as app:
        resp = await app.post(
            f"{MOODLE_URL}/webservice/rest/server.php",
            data={
                "wstoken": session.token,
                "wsfunction": "tool_mobile_get_autologin_key",
                "moodlewsrestformat": "json",
                "privatetoken": session.privatetoken,
            },
        )
        data = resp.json()
    if isinstance(data, dict) and "exception" in data:
        code = str(data.get("errorcode"))
        if code == "autologinkeygenerationlockout":
            raise RuntimeError(_lockout_message(str(data.get("message", ""))))
        raise MoodleError(code, str(data.get("message", "")))
    jar = httpx.Cookies()
    async with httpx.AsyncClient(
        timeout=30.0, headers={"User-Agent": USER_AGENT}, cookies=jar, follow_redirects=True
    ) as web:
        await web.get(
            data["autologinurl"],
            params={"userid": session.userid, "key": data["key"], "urltogo": f"{MOODLE_URL}/my/"},
        )
    return jar


async def fetch_page(path: str) -> str:
    global _jar
    if _jar is None:
        _jar = await _acquire()
    for attempt in range(2):
        async with httpx.AsyncClient(
            timeout=30.0, headers={"User-Agent": USER_AGENT}, cookies=_jar, follow_redirects=True
        ) as web:
            resp = await web.get(f"{MOODLE_URL}{path}")
        final = str(resp.url)
        if "/login/" not in final and "microsoftonline" not in final:
            return resp.text
        if attempt == 0:
            _jar = await _acquire()
    raise RuntimeError("Could not establish a Moodle web session for this page")
