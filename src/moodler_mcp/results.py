from datetime import UTC, datetime
from typing import Any

from bs4 import BeautifulSoup
from mcp.server.mcpserver import Context
from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel

from moodler_mcp.config import LOCAL_FILE_CLIENTS


def result(summary: str, data: BaseModel) -> Any:
    return CallToolResult(
        content=[TextContent(type="text", text=summary)],
        structured_content=data.model_dump(mode="json"),
    )


def iso(ts: int | float | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(int(ts), tz=UTC).isoformat()


def strip_html(html: str | None) -> str:
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)


def client_name(ctx: Context | None) -> str:
    if ctx is None:
        return ""
    params = getattr(ctx.session, "client_params", None)
    info = getattr(params, "client_info", None)
    return str(getattr(info, "name", "") or "").lower()


def is_local_file_client(ctx: Context | None) -> bool:
    name = client_name(ctx)
    return any(marker in name for marker in LOCAL_FILE_CLIENTS)


def can_ask(ctx: Context | None) -> bool:
    if ctx is None:
        return False
    caps = ctx.client_capabilities
    return bool(
        caps is not None and caps.elicitation is not None and caps.elicitation.form is not None
    )
