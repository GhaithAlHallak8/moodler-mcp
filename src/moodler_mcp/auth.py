import os
import re
import sys

from moodler_mcp.config import MOODLE_URL, STATE_DIR, STATE_FILE

_NO_BROWSER_MESSAGE = (
    "moodler-mcp could not find a compatible browser.\n"
    "Install one of the following and try again:\n"
    "  • Google Chrome: https://www.google.com/chrome/\n"
    "  • Or Playwright's bundled Chromium: `uv run playwright install chromium`"
)


async def _launch_browser(p, headless: bool):
    """Try bundled Chromium → system Chrome → Edge (Windows) → error."""
    attempts = [
        {},
        {"channel": "chrome"},
    ]
    if sys.platform == "win32":
        attempts.append({"channel": "msedge"})

    last_error: Exception | None = None
    for kwargs in attempts:
        try:
            return await p.chromium.launch(headless=headless, **kwargs)
        except Exception as exc:
            last_error = exc

    raise RuntimeError(_NO_BROWSER_MESSAGE) from last_error


_session_cache: dict | None = None


def _ensure_state_dir():
    os.makedirs(STATE_DIR, exist_ok=True)


async def _extract_sesskey(page) -> str:
    """Extract sesskey from a Moodle page's JavaScript config."""
    content = await page.content()
    match = re.search(r'"sesskey":"([^"]+)"', content)
    if match:
        return match.group(1)
    raise RuntimeError("Could not extract sesskey from Moodle page")


async def _extract_cookie(context) -> str:
    """Extract MoodleSession cookie from browser context."""
    cookies = await context.cookies(MOODLE_URL)
    for c in cookies:
        if c["name"] == "MoodleSession":
            return c["value"]
    raise RuntimeError("No MoodleSession cookie found")


async def _authenticate(headless: bool) -> dict:
    """Run Playwright to authenticate and return session info."""
    from playwright.async_api import async_playwright

    _ensure_state_dir()

    async with async_playwright() as p:
        browser = await _launch_browser(p, headless=headless)

        if os.path.exists(STATE_FILE) and headless:
            context = await browser.new_context(storage_state=STATE_FILE)
        else:
            context = await browser.new_context()

        page = await context.new_page()
        await page.goto(f"{MOODLE_URL}/my/", wait_until="networkidle")

        # If not on dashboard, SSO redirect is needed — relaunch visible
        if "/my/" not in page.url and headless:
            await browser.close()
            return await _authenticate(headless=False)

        # Wait for dashboard to fully load (handles SSO redirects)
        if "/my/" not in page.url:
            await page.wait_for_url("**/my/**", timeout=120000)

        cookie = await _extract_cookie(context)
        sesskey = await _extract_sesskey(page)

        await context.storage_state(path=STATE_FILE)
        await browser.close()

        return {"cookie": cookie, "sesskey": sesskey}


async def get_session() -> tuple[str, str]:
    """Get a valid (cookie, sesskey) pair. Authenticates if needed.

    Returns:
        Tuple of (MoodleSession cookie value, sesskey string)
    """
    global _session_cache

    if _session_cache is not None:
        return _session_cache["cookie"], _session_cache["sesskey"]

    _session_cache = await _authenticate(headless=True)
    return _session_cache["cookie"], _session_cache["sesskey"]


def clear_session():
    """Clear cached session, forcing re-authentication on next call."""
    global _session_cache
    _session_cache = None
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
