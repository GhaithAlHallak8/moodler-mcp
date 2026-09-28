import asyncio
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
from mcp.server.mcpserver.exceptions import ToolError

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


class LoginRequired(ToolError):
    def __init__(self) -> None:
        super().__init__(LOGIN_REQUIRED_MESSAGE)


@dataclass(frozen=True)
class Session:
    token: str
    privatetoken: str | None
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
    raise ToolError(_NO_BROWSER_MESSAGE) from last_error


def _decode_app_token(url: str, passport: str) -> tuple[str, str | None]:
    raw = base64.b64decode(url.split("token=", 1)[1]).decode()
    parts = raw.split(":::")
    expected = hashlib.md5(f"{MOODLE_URL}{passport}".encode()).hexdigest()
    if len(parts) < 2 or parts[0] != expected:
        raise ToolError("Moodle returned a token for a different site or passport")
    return parts[1], parts[2] if len(parts) > 2 else None


_IDP_SELECTORS = (
    "a.login-identityprovider-btn",
    ".potentialidplist a",
    "a[href*='authCAS=']",
)


async def _click_single_idp(page: Any) -> bool:
    """On a login page with exactly one identity provider (e.g. a CAS button), click it.

    launch.php sends the user through require_login(); sites whose SSO is an
    optional button rather than an automatic redirect would otherwise stall here.
    """
    for selector in _IDP_SELECTORS:
        with contextlib.suppress(Exception):
            links = await page.query_selector_all(selector)
            if len(links) == 1:
                await links[0].click()
                return True
    return False


async def _launch_link(page: Any) -> str | None:
    # iOS user agents / confirmed launches get an HTML page with a link instead of a redirect.
    with contextlib.suppress(Exception):
        href = await page.get_attribute("#launchapp", "href", timeout=500)
        if href and href.startswith("moodlemobile://"):
            return href
    return None


async def _acquire_tokens(context: Any, page: Any) -> tuple[str, str | None]:
    """Fetch a web service token via the mobile-app launch flow.

    Moodle only includes a private token when the user has just logged in, the
    request is over HTTPS and the user is not a site admin. The private token is
    only needed for web-session autologin, so a token without one is accepted.
    """
    captured: list[str] = []
    fallback: str | None = None

    def on_request(req: Any) -> None:
        if req.url.startswith("moodlemobile://"):
            captured.append(req.url)

    page.on("request", on_request)
    page.on("requestfailed", on_request)
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
            # Clearing the session forces a fresh login. If the site shows a login page
            # instead of redirecting to SSO, click its single identity provider and wait
            # (or let the user finish signing in) until Moodle hands back the token.
            deadline = time.monotonic() + BOOTSTRAP_TIMEOUT_MS / 1000
            clicked = False
            while not captured and time.monotonic() < deadline:
                link = await _launch_link(page)
                if link:
                    captured.append(link)
                    break
                if not clicked and "/login/" in page.url:
                    clicked = await _click_single_idp(page)
                await asyncio.sleep(0.5)
            if captured:
                token, private = _decode_app_token(captured[0], passport)
                if private:
                    return token, private
                fallback = token
            if fallback is not None:
                break
    finally:
        page.remove_listener("request", on_request)
        page.remove_listener("requestfailed", on_request)
    if fallback is not None:
        return fallback, None
    raise ToolError(
        "Moodle did not return a web service token. The sign-in window may have been "
        "closed before Moodle finished; run login_to_moodle again."
    )


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
        raise ToolError(f"Moodle error ({data.get('errorcode')}): {data.get('message')}")
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
            with contextlib.suppress(Exception):
                await page.goto(
                    f"{MOODLE_URL}/my/", wait_until="domcontentloaded", timeout=BOOTSTRAP_TIMEOUT_MS
                )
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
