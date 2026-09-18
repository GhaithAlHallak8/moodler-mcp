import base64
import html
import mimetypes
import os
import zipfile
from typing import Annotated
from urllib.parse import parse_qs, urlparse

from mcp.server.mcpserver import Context, Elicit, Resolve
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import BlobResourceContents, EmbeddedResource, TextContent, ToolAnnotations
from pydantic import BaseModel

from moodler_mcp import moodle_api as api
from moodler_mcp.asking import FileChoice
from moodler_mcp.client import download_file
from moodler_mcp.config import DOWNLOADS_DIR, EMBED_LIMIT_BYTES, MOODLE_URL
from moodler_mcp.files import OFFICE_SUFFIXES, file_to_content
from moodler_mcp.results import can_ask, is_local_file_client, iso, result, strip_html
from moodler_mcp.server import mcp, register_download

READ = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)


class Course(BaseModel):
    id: int
    fullname: str
    shortname: str
    category: str
    startdate: str | None
    enddate: str | None
    progress: float | None
    url: str


class CourseList(BaseModel):
    total: int
    courses: list[Course]


class FileRef(BaseModel):
    filename: str
    url: str
    size: int
    mimetype: str | None
    modified: str | None


class Module(BaseModel):
    cmid: int
    name: str
    modname: str
    instance: int
    url: str | None
    description: str
    visible: bool
    completion: int
    dates: list[str]
    files: list[FileRef]


class Section(BaseModel):
    id: int
    name: str
    summary: str
    visible: bool
    modules: list[Module]


class CourseContents(BaseModel):
    course_id: int
    sections: list[Section]


class ModuleContent(BaseModel):
    cmid: int
    course_id: int
    modname: str
    instance: int
    name: str
    description: str
    content: str | None
    external_url: str | None
    due: str | None
    files: list[FileRef]


def _file_ref(c: dict) -> FileRef:
    return FileRef(
        filename=c.get("filename", ""),
        url=c.get("fileurl", ""),
        size=int(c.get("filesize") or 0),
        mimetype=c.get("mimetype"),
        modified=iso(c.get("timemodified")),
    )


def _module(m: dict) -> Module:
    return Module(
        cmid=m["id"],
        name=html.unescape(m.get("name", "")),
        modname=m.get("modname", ""),
        instance=int(m.get("instance") or 0),
        url=m.get("url"),
        description=strip_html(m.get("description")),
        visible=bool(m.get("uservisible", m.get("visible", 1))),
        completion=int(m.get("completion") or 0),
        dates=[
            f"{d.get('label', '')} {iso(d.get('timestamp')) or ''}".strip()
            for d in m.get("dates", [])
        ],
        files=[_file_ref(c) for c in m.get("contents", []) if c.get("type") == "file"],
    )


def cmid_from(url_or_id: str | int) -> int:
    if isinstance(url_or_id, int) or str(url_or_id).isdigit():
        return int(url_or_id)
    query = parse_qs(urlparse(str(url_or_id)).query)
    if "id" not in query:
        raise ToolError(f"No course module id in {url_or_id}")
    return int(query["id"][0])


async def module_files(course_id: int, cmid: int) -> list[FileRef]:
    for section in await api.course_contents(course_id=course_id):
        for m in section.get("modules", []):
            if m["id"] == cmid:
                return [_file_ref(c) for c in m.get("contents", []) if c.get("type") == "file"]
    return []


@mcp.tool(title="List courses", annotations=READ)
async def list_courses(classification: str = "all", limit: int = 50) -> CourseList:
    """List your enrolled Moodle courses.

    Args:
        classification: 'all', 'inprogress', 'past' or 'future'
        limit: Max number of courses to return (max 50)
    """
    limit = min(limit, 50)
    data = await api.enrolled_courses(classification=classification, limit=limit)
    courses = [
        Course(
            id=c["id"],
            fullname=html.unescape(c.get("fullname", "")),
            shortname=html.unescape(c.get("shortname", "")),
            category=html.unescape(c.get("coursecategory", "")),
            startdate=iso(c.get("startdate")),
            enddate=iso(c.get("enddate")),
            progress=c.get("progress") if c.get("hasprogress") else None,
            url=c.get("viewurl", f"{MOODLE_URL}/course/view.php?id={c['id']}"),
        )
        for c in data.get("courses", [])
    ]
    return result(
        f"{len(courses)} course(s), classification={classification}.",
        CourseList(total=len(courses), courses=courses),
    )


@mcp.tool(title="Course contents", annotations=READ)
async def get_course_contents(course_id: int) -> CourseContents:
    """Get all sections, activities and files in a course, with course module ids (cmid)
    and direct file URLs for download_resource.

    Args:
        course_id: The Moodle course id
    """
    sections = [
        Section(
            id=s["id"],
            name=html.unescape(s.get("name", "")),
            summary=strip_html(s.get("summary")),
            visible=bool(s.get("uservisible", s.get("visible", 1))),
            modules=[_module(m) for m in s.get("modules", [])],
        )
        for s in await api.course_contents(course_id=course_id)
    ]
    count = sum(len(s.modules) for s in sections)
    return result(
        f"{len(sections)} section(s), {count} module(s).",
        CourseContents(course_id=course_id, sections=sections),
    )


async def _assignment_for(course_id: int, cmid: int) -> dict | None:
    data = await api.assignments(course_id=course_id)
    for course in data.get("courses", []):
        for a in course.get("assignments", []):
            if a.get("cmid") == cmid:
                return a
    return None


@mcp.tool(title="Module content", annotations=READ)
async def get_module_content(url: str | None = None, cmid: int | None = None) -> ModuleContent:
    """Get the content of one course module: assignment brief and attachments, page text,
    external URL, folder or resource files. Pass either the module URL or its cmid.
    For plain downloads call download_resource directly with the file URL.

    Args:
        url: Module URL such as '/mod/assign/view.php?id=570007'
        cmid: Course module id, alternative to url
    """
    if cmid is None:
        if url is None:
            raise ToolError("Pass url or cmid")
        cmid = cmid_from(url)
    cm = (await api.course_module(cmid=cmid))["cm"]
    course_id, modname, instance = int(cm["course"]), cm["modname"], int(cm["instance"])
    files = await module_files(course_id, cmid)
    content: str | None = None
    external: str | None = None
    due: str | None = None
    description = ""
    if modname == "assign":
        a = await _assignment_for(course_id, cmid)
        if a:
            description = strip_html(a.get("intro"))
            due = iso(a.get("duedate"))
            files = [_file_ref(f) for f in a.get("introattachments", [])] + files
    elif modname == "page":
        for p in (await api.pages_by_course(course_id=course_id)).get("pages", []):
            if p.get("coursemodule") == cmid:
                description = strip_html(p.get("intro"))
                content = strip_html(p.get("content"))
                files = [_file_ref(f) for f in p.get("contentfiles", [])] + files
    elif modname == "url":
        for u in (await api.urls_by_course(course_id=course_id)).get("urls", []):
            if u.get("coursemodule") == cmid:
                description = strip_html(u.get("intro"))
                external = u.get("externalurl")
    elif modname == "folder":
        for f in (await api.folders_by_course(course_id=course_id)).get("folders", []):
            if f.get("coursemodule") == cmid:
                description = strip_html(f.get("intro"))
    elif modname == "resource":
        for r in (await api.resources_by_course(course_id=course_id)).get("resources", []):
            if r.get("coursemodule") == cmid:
                description = strip_html(r.get("intro"))
                files = [_file_ref(f) for f in r.get("contentfiles", [])] or files
    data = ModuleContent(
        cmid=cmid,
        course_id=course_id,
        modname=modname,
        instance=instance,
        name=html.unescape(cm.get("name", "")),
        description=description,
        content=content,
        external_url=external,
        due=due,
        files=files,
    )
    return result(f"{modname} '{data.name}' with {len(files)} file(s).", data)


def _zip_listing(filepath: str) -> list[TextContent]:
    filename = os.path.basename(filepath)
    extract_dir = os.path.join(os.path.dirname(filepath), os.path.splitext(filename)[0])
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(filepath) as zf:
        zf.extractall(extract_dir)
    os.remove(filepath)
    lines = [
        f"# {filename} (zip archive; choose files to load)",
        "Use read_downloaded_file(path=...) with one of:",
        "",
    ]
    for root, _, names in os.walk(extract_dir):
        for name in sorted(names):
            fpath = os.path.join(root, name)
            rel = os.path.relpath(fpath, DOWNLOADS_DIR)
            lines.append(f"- `{rel}` ({os.path.getsize(fpath)} bytes)")
    return [TextContent(type="text", text="\n".join(lines))]


async def _resolve_download_url(url: str) -> str | list[FileRef]:
    if "pluginfile.php" in url:
        return url
    path = urlparse(url).path
    if "/mod/" not in path or "view.php" not in path:
        return url
    cmid = cmid_from(url)
    cm = (await api.course_module(cmid=cmid))["cm"]
    files = await module_files(int(cm["course"]), cmid)
    if not files:
        raise ToolError(f"Module {cmid} ({cm.get('modname')}) has no downloadable files")
    if len(files) == 1:
        return files[0].url
    return files


async def _choose_file(
    ctx: Context, url: str, choice: str | None = None
) -> Elicit[FileChoice] | FileChoice | None:
    if choice:
        return FileChoice(filename=choice)
    if not can_ask(ctx):
        return None
    target = await _resolve_download_url(url)
    if not isinstance(target, list):
        return None
    names = "\n".join(f"- {f.filename} ({f.size} bytes)" for f in target)
    return Elicit(f"This module has several files. Which one?\n{names}", FileChoice)


def _delivery_blocks(filepath: str, ctx: Context | None) -> list:
    uri = register_download(filepath)
    blocks: list = [TextContent(type="text", text=f"Saved to: {filepath}\nResource: {uri}")]
    size = os.path.getsize(filepath)
    if is_local_file_client(ctx) and size <= EMBED_LIMIT_BYTES:
        mime = mimetypes.guess_type(filepath)[0] or "application/octet-stream"
        with open(filepath, "rb") as fh:
            blob = base64.b64encode(fh.read()).decode()
        blocks.append(
            EmbeddedResource(
                type="resource", resource=BlobResourceContents(uri=uri, mime_type=mime, blob=blob)
            )
        )
    return blocks


@mcp.tool(title="Download resource", annotations=READ, structured_output=False)
async def download_resource(
    url: str,
    pages: str | None = None,
    choice: str | None = None,
    ctx: Context | None = None,
    picked: Annotated[FileChoice | None, Resolve(_choose_file)] = None,
) -> list:
    """Download a Moodle file and return its content plus the local file path.

    Accepts a pluginfile URL (from get_course_contents or get_module_content) or a
    '/mod/resource/view.php?id=...' or '/mod/folder/view.php?id=...' URL. A folder with
    several files returns the list of files to choose from; pass choice=<filename> or the
    file URL to download one of them.

    Content handling: text files as text (max 1MB), images inline (max 5MB), PDFs as page
    images (default first 30 pages; use pages like '1-5,7'), zips as a file listing for
    read_downloaded_file, .docx as markdown plus images, .pptx as one block per slide,
    .xlsx as markdown tables. Other binaries return only the local path. On local clients
    the file itself is attached as a resource.

    Args:
        url: Moodle file, resource or folder URL
        pages: 1-indexed page, slide or sheet selection like '1-5,7,10-12'
        choice: Filename to pick when the URL is a folder with several files
    """
    target = await _resolve_download_url(url)
    if isinstance(target, list):
        wanted = (picked.filename if picked else None) or choice
        match = next((f for f in target if f.filename == wanted), None)
        if match is None:
            lines = [
                "Several files in this module; call again with choice=<filename> or a file URL:"
            ]
            lines += [f"- {f.filename} ({f.size} bytes): {f.url}" for f in target]
            return [TextContent(type="text", text="\n".join(lines))]
        target = match.url
    if ctx is not None:
        await ctx.report_progress(1, 3, "Downloading")
    filepath = await download_file(target)
    if ctx is not None:
        await ctx.report_progress(2, 3, "Extracting")
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in OFFICE_SUFFIXES and zipfile.is_zipfile(filepath):
        blocks = _zip_listing(filepath)
    else:
        blocks = file_to_content(filepath, pages=pages)
        blocks.extend(_delivery_blocks(filepath, ctx))
    if ctx is not None:
        await ctx.report_progress(3, 3, "Done")
        await ctx.notify_resources_changed()
    return blocks


@mcp.tool(title="Read downloaded file", annotations=READ, structured_output=False)
async def read_downloaded_file(
    path: str, pages: str | None = None, ctx: Context | None = None
) -> list:
    """Read a file from the local downloads directory. Only use paths listed by a prior
    download_resource zip listing, copied verbatim.

    Args:
        path: Relative path under the downloads dir from a zip listing
        pages: 1-indexed selection like '1-5,7' for PDF pages, slides or sheets
    """
    if ".." in path or path.startswith("/"):
        raise ToolError("Invalid path")
    filepath = os.path.join(DOWNLOADS_DIR, path)
    if not os.path.exists(filepath):
        raise ToolError(f"Not found: {path}")
    blocks = file_to_content(filepath, pages=pages)
    blocks.extend(_delivery_blocks(filepath, ctx))
    return blocks
