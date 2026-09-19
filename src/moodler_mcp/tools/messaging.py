from mcp.types import ToolAnnotations
from pydantic import BaseModel

from moodler_mcp import moodle_api as api
from moodler_mcp.results import iso, result, strip_html
from moodler_mcp.server import mcp

READ = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)


class Notification(BaseModel):
    id: int
    subject: str
    text: str
    created: str | None
    read: bool
    url: str | None
    component: str | None
    eventtype: str | None


class NotificationList(BaseModel):
    unread: int
    total: int
    notifications: list[Notification]


class Message(BaseModel):
    id: int
    from_user_id: int
    text: str
    created: str | None


class Conversation(BaseModel):
    id: int
    name: str
    type: int
    members: list[str]
    unread: int
    last_message: Message | None


class ConversationList(BaseModel):
    total: int
    conversations: list[Conversation]


class ConversationMessages(BaseModel):
    conversation_id: int
    members: dict[int, str]
    messages: list[Message]


def _message(m: dict) -> Message:
    return Message(
        id=m["id"],
        from_user_id=m["useridfrom"],
        text=strip_html(m.get("text")),
        created=iso(m.get("timecreated")),
    )


@mcp.tool(title="Notifications", annotations=READ)
async def get_notifications(limit: int = 20, unread_only: bool = False) -> NotificationList:
    """Your Moodle notifications: announcements, grade releases, forum digests, due reminders.

    Args:
        limit: Max notifications to return (max 100)
        unread_only: Only unread notifications
    """
    limit = min(limit, 100)
    data = await api.notifications(limit=100 if unread_only else limit, offset=0)
    items = [
        Notification(
            id=n["id"],
            subject=n.get("subject", ""),
            text=strip_html(n.get("fullmessagehtml") or n.get("fullmessage") or n.get("text")),
            created=iso(n.get("timecreated")),
            read=bool(n.get("read")),
            url=n.get("contexturl"),
            component=n.get("component"),
            eventtype=n.get("eventtype"),
        )
        for n in data.get("notifications", [])
        if not unread_only or not n.get("read")
    ][:limit]
    unread = int(data.get("unreadcount") or 0)
    return result(
        f"{len(items)} notification(s), {unread} unread.",
        NotificationList(unread=unread, total=len(items), notifications=items),
    )


@mcp.tool(title="List conversations", annotations=READ)
async def list_conversations(limit: int = 20) -> ConversationList:
    """Your message conversations, most recent first.

    Args:
        limit: Max conversations (max 50)
    """
    user_id = await api.current_user_id()
    data = await api.conversations(user_id=user_id, limit=min(limit, 50))
    convs = []
    for c in data.get("conversations", []):
        msgs = c.get("messages", [])
        convs.append(
            Conversation(
                id=c["id"],
                name=c.get("name")
                or ", ".join(m.get("fullname", "") for m in c.get("members", [])),
                type=int(c.get("type") or 0),
                members=[m.get("fullname", "") for m in c.get("members", [])],
                unread=int(c.get("unreadcount") or 0),
                last_message=_message(msgs[0]) if msgs else None,
            )
        )
    return result(
        f"{len(convs)} conversation(s).", ConversationList(total=len(convs), conversations=convs)
    )


@mcp.tool(title="Conversation messages", annotations=READ)
async def get_conversation(conversation_id: int, limit: int = 50) -> ConversationMessages:
    """Messages in one conversation, newest first.

    Args:
        conversation_id: From list_conversations
        limit: Max messages (max 200)
    """
    user_id = await api.current_user_id()
    data = await api.conversation_messages(
        user_id=user_id, conversation_id=conversation_id, limit=min(limit, 200)
    )
    members = {int(m["id"]): m.get("fullname", "") for m in data.get("members", [])}
    messages = [_message(m) for m in data.get("messages", [])]
    return result(
        f"{len(messages)} message(s).",
        ConversationMessages(conversation_id=conversation_id, members=members, messages=messages),
    )
