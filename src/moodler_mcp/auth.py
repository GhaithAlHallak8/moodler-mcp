import os
import re

from moodler_mcp.config import MOODLE_URL, STATE_DIR, STATE_FILE

_session_cache: dict | None = None


def _ensure_state_dir():
    os.makedirs(STATE_DIR, exist_ok=True)


def _extract_sesskey(page) -> str:
    """Extract sesskey from a Moodle page's JavaScript config."""
    content = page.content()
    match = re.search(r'"sesskey":"([^"]+)"', content)
    if match:
        return match.group(1)
    raise RuntimeError("Could not extract sesskey from Moodle page")


def _extract_cookie(context) -> str:
    """Extract MoodleSession cookie from browser context."""
    cookies = context.cookies(MOODLE_URL)
    for c in cookies:
        if c["name"] == "MoodleSession":
            return c["value"]
    raise RuntimeError("No MoodleSession cookie found")


def _authenticate(headless: bool) -> dict:
    """Run Playwright to authenticate and return session info."""
    from playwright.sync_api import sync_playwright

    _ensure_state_dir()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)

        if os.path.exists(STATE_FILE) and headless:
            context = browser.new_context(storage_state=STATE_FILE)
        else:
            context = browser.new_context()

        page = context.new_page()
        page.goto(f"{MOODLE_URL}/my/", wait_until="networkidle")

        # If not on dashboard, SSO redirect is needed — relaunch visible
        if "/my/" not in page.url and headless:
            browser.close()
            return _authenticate(headless=False)

        # Wait for dashboard to fully load (handles SSO redirects)
        if "/my/" not in page.url:
            page.wait_for_url("**/my/**", timeout=120000)

        cookie = _extract_cookie(context)
        sesskey = _extract_sesskey(page)

        context.storage_state(path=STATE_FILE)
        browser.close()

        return {"cookie": cookie, "sesskey": sesskey}


def get_session() -> tuple[str, str]:
    """Get a valid (cookie, sesskey) pair. Authenticates if needed.

    Returns:
        Tuple of (MoodleSession cookie value, sesskey string)
    """
    global _session_cache

    if _session_cache is not None:
        return _session_cache["cookie"], _session_cache["sesskey"]

    _session_cache = _authenticate(headless=True)
    return _session_cache["cookie"], _session_cache["sesskey"]


def clear_session():
    """Clear cached session, forcing re-authentication on next call."""
    global _session_cache
    _session_cache = None
