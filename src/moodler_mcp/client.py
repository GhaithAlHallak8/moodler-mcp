import os
import re
from urllib.parse import unquote, urlparse

import httpx

from moodler_mcp.auth import clear_session
from moodler_mcp.auth import get_session as _get_session
from moodler_mcp.config import MOODLE_URL, STATE_DIR, USER_AGENT

DOWNLOADS_DIR = os.path.join(STATE_DIR, "downloads")


async def _clear_and_get_session() -> tuple[str, str]:
    clear_session()
    return await _get_session()


_client = httpx.AsyncClient(
    timeout=30.0,
    headers={"User-Agent": USER_AGENT},
)


async def call_moodle(methodname: str, **args) -> dict:
    """Call a Moodle AJAX web service function.

    Args:
        methodname: The Moodle web service function name
        **args: Arguments to pass to the function

    Returns:
        The response data dict
    """
    cookie, sesskey = await _get_session()

    url = f"{MOODLE_URL}/lib/ajax/service.php"
    params = {"sesskey": sesskey, "info": methodname}
    body = [{"index": 0, "methodname": methodname, "args": args}]

    try:
        resp = await _client.post(
            url,
            params=params,
            json=body,
            cookies={"MoodleSession": cookie},
        )
        resp.raise_for_status()
    except httpx.TimeoutException as err:
        raise RuntimeError(f"Request to Moodle timed out ({methodname})") from err
    except httpx.HTTPError as e:
        raise RuntimeError(f"HTTP error calling Moodle: {type(e).__name__}: {e}") from e

    results = resp.json()
    result = results[0]

    if result.get("error"):
        exc = result.get("exception", {})
        error_msg = exc.get("message", "Unknown error")
        errorcode = exc.get("errorcode", "?")

        # Session expired, clear cache and retry once
        if "session" in error_msg.lower() or errorcode == "servicerequireslogin":
            cookie, sesskey = await _clear_and_get_session()
            params["sesskey"] = sesskey
            resp = await _client.post(
                url,
                params=params,
                json=body,
                cookies={"MoodleSession": cookie},
            )
            resp.raise_for_status()
            results = resp.json()
            result = results[0]

            if result.get("error"):
                exc = result.get("exception", {})
                raise RuntimeError(
                    f"Moodle error ({exc.get('errorcode', '?')}): "
                    f"{exc.get('message', 'Unknown error')}"
                )

            return result.get("data", result)

        raise RuntimeError(f"Moodle error ({errorcode}): {error_msg}")

    return result.get("data", result)


async def fetch_page(path: str) -> str:
    """Fetch an HTML page from Moodle using the session cookie.

    Args:
        path: URL path like '/course/view.php?id=123'

    Returns:
        The HTML content string
    """
    cookie, _ = await _get_session()
    url = f"{MOODLE_URL}{path}"

    try:
        resp = await _client.get(url, cookies={"MoodleSession": cookie})
        resp.raise_for_status()
    except httpx.TimeoutException as err:
        raise RuntimeError(f"Request to Moodle timed out ({path})") from err
    except httpx.HTTPError as e:
        raise RuntimeError(f"HTTP error fetching page: {type(e).__name__}: {e}") from e

    # Check if redirected to login (session expired)
    if "/login/" in str(resp.url):
        cookie, _ = await _clear_and_get_session()
        resp = await _client.get(url, cookies={"MoodleSession": cookie})
        resp.raise_for_status()
        if "/login/" in str(resp.url):
            raise RuntimeError("Session expired and re-authentication failed")

    return resp.text


async def download_file(url: str) -> str:
    """Download a file from Moodle, following redirects.

    Uses a dedicated client with a cookie jar so session cookies persist
    across the redirect chain (view.php -> pluginfile.php -> actual file).

    Args:
        url: Full Moodle URL or path (e.g. '/mod/resource/view.php?id=123')

    Returns:
        Local file path where the file was saved
    """
    if url.startswith("/"):
        url = f"{MOODLE_URL}{url}"

    cookie, _ = await _get_session()
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)

    cookies = httpx.Cookies()
    hostname = urlparse(MOODLE_URL).hostname
    assert hostname is not None, "MOODLE_URL must have a valid hostname"
    cookies.set("MoodleSession", cookie, domain=str(hostname))

    async with httpx.AsyncClient(
        timeout=60.0,
        headers={"User-Agent": USER_AGENT},
        cookies=cookies,
        follow_redirects=True,
        max_redirects=10,
    ) as dl_client:
        try:
            resp = await dl_client.get(url)
            resp.raise_for_status()
        except httpx.TimeoutException as err:
            raise RuntimeError(f"Download timed out ({url})") from err
        except httpx.HTTPError as e:
            raise RuntimeError(f"Download failed: {type(e).__name__}: {e}") from e

        if "/login/" in str(resp.url):
            cookie, _ = await _clear_and_get_session()
            cookies.set("MoodleSession", cookie, domain=str(hostname))
            resp = await dl_client.get(url)
            resp.raise_for_status()
            if "/login/" in str(resp.url):
                raise RuntimeError("Session expired and re-authentication failed")

    filename = None
    cd = resp.headers.get("content-disposition", "")
    if "filename=" in cd:
        match = re.search(r'filename[*]?=["\']?(?:UTF-8\'\')?([^"\';]+)', cd)
        if match:
            filename = unquote(match.group(1).strip())

    if not filename:
        path = urlparse(str(resp.url)).path
        filename = unquote(path.split("/")[-1]) or "download"

    filepath = os.path.join(DOWNLOADS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(resp.content)

    return filepath
