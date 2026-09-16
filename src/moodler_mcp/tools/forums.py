from mcp.types import ToolAnnotations
from pydantic import BaseModel

from moodler_mcp import moodle_api as api
from moodler_mcp.results import iso, result, strip_html
from moodler_mcp.server import mcp

READ = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)


class Forum(BaseModel):
    forum_id: int
    cmid: int
    name: str
    type: str
    intro: str
    discussions: int
    unread_posts: int


class ForumList(BaseModel):
    course_id: int
    total: int
    forums: list[Forum]


class Discussion(BaseModel):
    discussion_id: int
    first_post_id: int
    subject: str
    author: str
    created: str | None
    modified: str | None
    replies: int
    unread: int
    pinned: bool
    locked: bool
    preview: str


class DiscussionList(BaseModel):
    forum_id: int
    total: int
    discussions: list[Discussion]


class PostAttachment(BaseModel):
    filename: str
    url: str
    size: int


class Post(BaseModel):
    post_id: int
    parent_id: int | None
    subject: str
    author: str
    created: str | None
    message: str
    attachments: list[PostAttachment]


class DiscussionPosts(BaseModel):
    discussion_id: int
    total: int
    posts: list[Post]


@mcp.tool(title="List forums", annotations=READ)
async def list_forums(course_id: int) -> ForumList:
    """Forums in a course, including the announcements forum.

    Args:
        course_id: The Moodle course id
    """
    forums = [
        Forum(
            forum_id=f["id"],
            cmid=f["cmid"],
            name=f.get("name", ""),
            type=f.get("type", ""),
            intro=strip_html(f.get("intro")),
            discussions=int(f.get("numdiscussions") or 0),
            unread_posts=int(f.get("unreadpostscount") or 0),
        )
        for f in await api.forums(course_id=course_id)
    ]
    return result(
        f"{len(forums)} forum(s).", ForumList(course_id=course_id, total=len(forums), forums=forums)
    )


@mcp.tool(title="List discussions", annotations=READ)
async def list_discussions(forum_id: int, limit: int = 20) -> DiscussionList:
    """Discussions in a forum, most recently modified first.

    Args:
        forum_id: Forum instance id from list_forums
        limit: Max discussions (max 100)
    """
    data = await api.discussions(forum_id=forum_id, page=0, perpage=min(limit, 100))
    items = [
        Discussion(
            discussion_id=d["discussion"],
            first_post_id=d["id"],
            subject=d.get("subject") or d.get("name", ""),
            author=d.get("userfullname", ""),
            created=iso(d.get("created")),
            modified=iso(d.get("timemodified")),
            replies=int(d.get("numreplies") or 0),
            unread=int(d.get("numunread") or 0),
            pinned=bool(d.get("pinned")),
            locked=bool(d.get("locked")),
            preview=strip_html(d.get("message"))[:300],
        )
        for d in data.get("discussions", [])
    ]
    return result(
        f"{len(items)} discussion(s).",
        DiscussionList(forum_id=forum_id, total=len(items), discussions=items),
    )


@mcp.tool(title="Discussion posts", annotations=READ)
async def get_discussion(discussion_id: int) -> DiscussionPosts:
    """All posts in a discussion in chronological order, with attachments.

    Args:
        discussion_id: From list_discussions
    """
    data = await api.discussion_posts(discussion_id=discussion_id)
    posts = [
        Post(
            post_id=p["id"],
            parent_id=p.get("parentid") if p.get("hasparent") else None,
            subject=p.get("subject", ""),
            author=(p.get("author") or {}).get("fullname", ""),
            created=iso(p.get("timecreated")),
            message=strip_html(p.get("message")),
            attachments=[
                PostAttachment(
                    filename=a.get("filename", ""),
                    url=a.get("fileurl", a.get("url", "")),
                    size=int(a.get("filesize") or 0),
                )
                for a in p.get("attachments", [])
            ],
        )
        for p in data.get("posts", [])
    ]
    return result(
        f"{len(posts)} post(s).",
        DiscussionPosts(discussion_id=discussion_id, total=len(posts), posts=posts),
    )
