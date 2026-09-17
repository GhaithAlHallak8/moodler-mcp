from collections.abc import Callable

from mcp.server.mcpserver import Context, Elicit
from pydantic import BaseModel, Field

from moodler_mcp.results import can_ask


class Approval(BaseModel):
    confirm: bool = Field(description="True to proceed, false to cancel")


NO_APPROVAL = Approval(confirm=False)


class FileChoice(BaseModel):
    filename: str = Field(description="Exact filename to download")


def approval(message: str) -> Callable[..., Elicit[Approval] | Approval]:
    def resolver(ctx: Context, confirm: bool = False) -> Elicit[Approval] | Approval:
        if confirm or not can_ask(ctx):
            return Approval(confirm=confirm)
        return Elicit(message, Approval)

    return resolver
