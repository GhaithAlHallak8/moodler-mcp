import json
import os
import re
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
from mcp.server.mcpserver.exceptions import ToolError

from moodler_mcp.auth import LoginRequired, load_session
from moodler_mcp.config import DOWNLOADS_DIR, MOODLE_URL, USER_AGENT

REST_URL = f"{MOODLE_URL}/webservice/rest/server.php"
UPLOAD_URL = f"{MOODLE_URL}/webservice/upload.php"

_http = httpx.AsyncClient(timeout=60.0, headers={"User-Agent": USER_AGENT})


class MoodleError(ToolError):
    def __init__(self, errorcode: str, message: str) -> None:
        self.errorcode = errorcode
        self.message = message
        super().__init__(f"Moodle error ({errorcode}): {message}")


def flatten(prefix: str, value: Any, out: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            flatten(f"{prefix}[{k}]", v, out)
    elif isinstance(value, list | tuple):
        for i, v in enumerate(value):
            flatten(f"{prefix}[{i}]", v, out)
    elif isinstance(value, bool):
        out[prefix] = int(value)
    elif value is not None:
        out[prefix] = value


def encode_args(args: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in args.items():
        flatten(k, v, out)
    return out


def _raise_for_moodle_error(data: Any) -> None:
    if isinstance(data, dict) and "exception" in data:
        code = str(data.get("errorcode", "unknown"))
        message = str(data.get("message", "Unknown error"))
        if code == "invalidtoken" or (code == "accessexception" and "token" in message.lower()):
            raise LoginRequired()
        raise MoodleError(code, message)


async def call(function: str, **args: Any) -> Any:
    session = load_session()
    form: dict[str, Any] = {
        "wstoken": session.token,
        "wsfunction": function,
        "moodlewsrestformat": "json",
    }
    form.update(encode_args(args))
    try:
        resp = await _http.post(REST_URL, data=form)
        resp.raise_for_status()
    except httpx.TimeoutException as exc:
        raise ToolError(f"Request to Moodle timed out ({function})") from exc
    except httpx.HTTPError as exc:
        raise ToolError(f"HTTP error calling Moodle: {type(exc).__name__}: {exc}") from exc
    data = resp.json()
    _raise_for_moodle_error(data)
    return data


def webservice_url(url: str) -> str:
    if url.startswith("/"):
        url = f"{MOODLE_URL}{url}"
    if urlparse(url).netloc.lower() != urlparse(MOODLE_URL).netloc.lower():
        raise ToolError(f"Refusing to download from a host other than {MOODLE_URL}: {url}")
    if "/webservice/pluginfile.php/" in url:
        return url
    return url.replace("/pluginfile.php/", "/webservice/pluginfile.php/", 1)


def _filename_from(resp: httpx.Response) -> str:
    cd = resp.headers.get("content-disposition", "")
    match = re.search(r"filename[*]?=[\"']?(?:UTF-8'')?([^\"';]+)", cd)
    raw = unquote(match.group(1).strip()) if match else unquote(urlparse(str(resp.url)).path)
    name = os.path.basename(raw.replace("\\", "/")).strip()
    if name in {"", ".", ".."}:
        return "download"
    return name


async def download_file(url: str) -> str:
    session = load_session()
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    target = webservice_url(url)
    try:
        async with _http.stream(
            "GET", target, params={"token": session.token}, follow_redirects=True
        ) as resp:
            resp.raise_for_status()
            if "application/json" in resp.headers.get("content-type", ""):
                body = await resp.aread()
                _raise_for_moodle_error(json.loads(body))
            filename = _filename_from(resp)
            filepath = os.path.join(DOWNLOADS_DIR, filename)
            with open(filepath, "wb") as fh:
                async for chunk in resp.aiter_bytes():
                    fh.write(chunk)
    except httpx.TimeoutException as exc:
        raise ToolError(f"Download timed out ({url})") from exc
    except httpx.HTTPError as exc:
        raise ToolError(f"Download failed: {type(exc).__name__}: {exc}") from exc
    return filepath


async def upload_draft(path: str) -> int:
    session = load_session()
    with open(path, "rb") as fh:
        files = {"file_1": (os.path.basename(path), fh.read())}
    resp = await _http.post(
        UPLOAD_URL,
        data={"token": session.token, "filearea": "draft", "itemid": 0, "filepath": "/"},
        files=files,
    )
    resp.raise_for_status()
    data = resp.json()
    _raise_for_moodle_error(data)
    if not isinstance(data, list) or not data or "itemid" not in data[0]:
        raise ToolError(f"Upload failed: {data}")
    return int(data[0]["itemid"])
