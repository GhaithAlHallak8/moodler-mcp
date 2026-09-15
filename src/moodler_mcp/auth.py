import base64
import contextlib
import hashlib
import json
import os
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from moodler_mcp.config import (
    BOOTSTRAP_TIMEOUT_MS,
    LEGACY_STATE_FILE,
    MOBILE_SERVICE,
    MOODLE_URL,
    STATE_DIR,
    TOKEN_FILE,
    USER_AGENT,
)

LOGIN_REQUIRED_MESSAGE = (
    "Not signed in to Moodle. Call the login_to_moodle tool once; a browser window will open "
    "for single sign-on and the resulting token is stored locally for future sessions."
)

_NO_BROWSER_MESSAGE = (
    "moodler-mcp could not find a compatible browser.\n"
    "Install one of the following and try again:\n"
    "  • Google Chrome: https://www.google.com/chrome/\n"
    "  • Or Playwright's bundled Chromium: `uv run playwright install chromium`"
)

Progress = Callable[[float, str], Awaitable[None]]


class LoginRequired(RuntimeError):
    def __init__(self) -> None:
        super().__init__(LOGIN_REQUIRED_MESSAGE)


@dataclass(frozen=True)
class Session:
    token: str
    privatetoken: str
    userid: int
    username: str
    site_release: str
    created_at: str


_session: Session | None = None


def load_session() -> Session:
    global _session
    if _session is not None:
        return _session
    try:
        with open(TOKEN_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        _session = Session(**data)
    except (OSError, ValueError, TypeError) as exc:
        raise LoginRequired() from exc
    return _session


def save_session(session: Session) -> None:
    global _session
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = f"{TOKEN_FILE}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(asdict(session), fh)
    os.chmod(tmp, 0o600)
    os.replace(tmp, TOKEN_FILE)
    _session = session


def clear_session() -> None:
    global _session
    _session = None
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)


async def _launch_browser(p: Any) -> Any:
    attempts: list[dict[str, str]] = [{}, {"channel": "chrome"}]
    if sys.platform == "win32":
        attempts.append({"channel": "msedge"})
    last_error: Exception | None = None
    for kwargs in attempts:
        try:
            return await p.chromium.launch(headless=False, **kwargs)
        except Exception as exc:
            last_error = exc
    raise RuntimeError(_NO_BROWSER_MESSAGE) from last_error


def _decode_app_token(url: str, passport: str) -> tuple[str, str | None]:
    raw = base64.b64decode(url.split("token=", 1)[1]).decode()
    parts = raw.split(":::")
    expected = hashlib.md5(f"{MOODLE_URL}{passport}".encode()).hexdigest()
    if len(parts) < 2 or parts[0] != expected:
        raise RuntimeError("Moodle returned a token for a different site or passport")
    return parts[1], parts[2] if len(parts) > 2 else None


async def _acquire_tokens(context: Any, page: Any) -> tuple[str, str]:
    captured: list[str] = []

    def on_request(req: Any) -> None:
        if req.url.startswith("moodlemobile://"):
            captured.append(req.url)

    page.on("request", on_request)
    try:
        for _ in range(2):
            await context.clear_cookies(name="MoodleSession")
            passport = f"{time.time():.4f}"
            captured.clear()
            launch = (
                f"{MOODLE_URL}/admin/tool/mobile/launch.php?service={MOBILE_SERVICE}"
                f"&passport={passport}&urlscheme=moodlemobile"
            )
            with contextlib.suppress(Exception):
                await page.goto(launch, wait_until="networkidle", timeout=60_000)
            if captured:
                token, private = _decode_app_token(captured[0], passport)
                if private:
                    return token, private
    finally:
        page.remove_listener("request", on_request)
    raise RuntimeError("Moodle issued a token without a private token. Run login_to_moodle again.")


async def _site_info(token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": USER_AGENT}) as http:
        resp = await http.post(
            f"{MOODLE_URL}/webservice/rest/server.php",
            data={
                "wstoken": token,
                "wsfunction": "core_webservice_get_site_info",
                "moodlewsrestformat": "json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    if "exception" in data:
        raise RuntimeError(f"Moodle error ({data.get('errorcode')}): {data.get('message')}")
    return data


async def bootstrap(progress: Progress | None = None) -> Session:
    from playwright.async_api import async_playwright

    async def report(step: float, message: str) -> None:
        if progress is not None:
            await progress(step, message)

    os.makedirs(STATE_DIR, exist_ok=True)
    async with async_playwright() as p:
        await report(1, "Opening browser for single sign-on")
        browser = await _launch_browser(p)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(f"{MOODLE_URL}/my/", wait_until="networkidle")
            if "/my/" not in page.url:
                await page.wait_for_url("**/my/**", timeout=BOOTSTRAP_TIMEOUT_MS)
            await report(2, "Requesting a web service token")
            token, private = await _acquire_tokens(context, page)
        finally:
            await browser.close()

    await report(3, "Saving token")
    info = await _site_info(token)
    session = Session(
        token=token,
        privatetoken=private,
        userid=int(info["userid"]),
        username=str(info.get("username", "")),
        site_release=str(info.get("release", "")),
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    save_session(session)
    if os.path.exists(LEGACY_STATE_FILE):
        os.remove(LEGACY_STATE_FILE)
    return session
