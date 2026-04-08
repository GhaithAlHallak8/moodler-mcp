import json
from datetime import datetime, timezone

from moodler_mcp.client import download_file, fetch_page
from moodler_mcp.moodle_api import get_course_sections, list_enrolled_courses
from moodler_mcp.server import mcp


def _format_course(c: dict) -> dict:
    result = {
        "id": c["id"],
        "fullname": c.get("fullname", ""),
        "shortname": c.get("shortname", ""),
        "category": c.get("coursecategory", ""),
    }
    if c.get("startdate"):
        result["startdate"] = datetime.fromtimestamp(
            c["startdate"], tz=timezone.utc
        ).isoformat()
    if c.get("enddate") and c["enddate"] != 0:
        result["enddate"] = datetime.fromtimestamp(
            c["enddate"], tz=timezone.utc
        ).isoformat()
    return result


@mcp.tool()
async def list_courses(classification: str = "all", limit: int = 50) -> str:
    """List your enrolled Moodle courses.

    Args:
        classification: Filter by 'all', 'inprogress', 'past', or 'future'
        limit: Max number of courses to return (max 50)
    """
    limit = min(limit, 50)
    data = await list_enrolled_courses(
        classification=classification,
        limit=limit,
    )
    courses = [_format_course(c) for c in data.get("courses", [])]
    return json.dumps({"total": len(courses), "courses": courses}, indent=2)


@mcp.tool()
async def get_course_contents(course_id: int) -> str:
    """Get all sections, activities, and resources within a course.

    Args:
        course_id: The Moodle course ID
    """
    sections = await get_course_sections(course_id=course_id)
    return json.dumps(sections, indent=2)


_TEXT_SUFFIXES = {
    ".py", ".txt", ".csv", ".json", ".ipynb", ".md", ".html", ".htm",
    ".xml", ".yaml", ".yml", ".java", ".c", ".cpp", ".h", ".js", ".ts",
    ".css", ".sql", ".r", ".tex", ".ini", ".cfg", ".toml", ".sh", ".bat",
}

_IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

# this is because formats are technically zip containers, but we must NOT auto-extract
_OFFICE_SUFFIXES = {
    ".docx", ".docm", ".dotx", ".dotm",
    ".xlsx", ".xlsm", ".xltx", ".xltm",
    ".pptx", ".pptm", ".potx", ".potm",
    ".odt", ".ods", ".odp",
}

MAX_TEXT_BYTES = 1_000_000  # ~250K tokens
MAX_PDF_PAGES = 30
MAX_IMAGE_BYTES = 5_000_000
# Host MCP clients cap tool results at 1MB; keep image bytes well below the cap.
PDF_RESPONSE_BUDGET_BYTES = 650_000
PDF_RENDER_DPI = 110  # lower DPI = smaller output; 110 keeps text readable
PDF_JPEG_QUALITY = 75


def _parse_pages(pages: str | None, total: int) -> list[int]:
    """Parse a page range string like '1-5,7,9-11' into a sorted list of 0-indexed ints.

    Returns all pages if `pages` is None or empty.
    """
    if not pages:
        return list(range(total))
    result: set[int] = set()
    for part in pages.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            for p in range(int(start), int(end) + 1):
                if 1 <= p <= total:
                    result.add(p - 1)
        else:
            p = int(part)
            if 1 <= p <= total:
                result.add(p - 1)
    return sorted(result)


def _file_to_content(filepath: str, pages: str | None = None):
    """Convert a file to MCP content blocks Claude.ai can render.

    Args:
        filepath: Path to the file
        pages: For PDFs only — page range like "1-5,7" (1-indexed). None = first MAX_PDF_PAGES.

    Returns either a single content block or a list (for PDFs with multiple pages).
    """
    import base64
    import os as _os

    from mcp.types import ImageContent, TextContent

    filename = _os.path.basename(filepath)
    ext = _os.path.splitext(filepath)[1].lower()
    size = _os.path.getsize(filepath)

    if ext in _TEXT_SUFFIXES:
        truncated = False
        with open(filepath, "r", errors="replace") as f:
            text = f.read(MAX_TEXT_BYTES + 1)
        if len(text) > MAX_TEXT_BYTES:
            text = text[:MAX_TEXT_BYTES]
            truncated = True
        header = f"# {filename}\nLocal path: {filepath}"
        if truncated:
            header += (
                f"\n[TRUNCATED — showing first {MAX_TEXT_BYTES} of {size} bytes. "
                f"Use your host's local file reader on the path above for the full file.]"
            )
        return TextContent(type="text", text=f"{header}\n\n{text}")

    if ext in _IMAGE_MIME:
        if size > MAX_IMAGE_BYTES:
            return TextContent(
                type="text",
                text=f"# {filename}\n[Image too large: {size} bytes > {MAX_IMAGE_BYTES} limit]",
            )
        with open(filepath, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return ImageContent(type="image", data=data, mimeType=_IMAGE_MIME[ext])

    if ext == ".pdf":
        import pymupdf

        doc = pymupdf.open(filepath)
        total_pages = len(doc)

        if pages:
            page_indices = _parse_pages(pages, total_pages)
            header = (
                f"# {filename} ({total_pages} pages, rendering: {pages})\n"
                f"Local path: {filepath}"
            )
        else:
            page_indices = list(range(min(total_pages, MAX_PDF_PAGES)))
            header = f"# {filename} ({total_pages} pages)\nLocal path: {filepath}"
            if len(page_indices) < total_pages:
                header += (
                    f"\n[TRUNCATED — rendering first {len(page_indices)} of {total_pages} pages. "
                    f"Call again with pages='X-Y' to get specific pages.]"
                )

        blocks: list = [TextContent(type="text", text=header)]
        # Fit as many requested pages as possible into the response budget.
        # JPEG is much smaller than PNG for document scans / dense text.
        used = 0
        rendered = 0
        skipped_first: int | None = None
        for i in page_indices:
            pix = doc[i].get_pixmap(dpi=PDF_RENDER_DPI)
            img_bytes = pix.tobytes("jpeg", jpg_quality=PDF_JPEG_QUALITY)
            if used + len(img_bytes) > PDF_RESPONSE_BUDGET_BYTES and rendered > 0:
                skipped_first = i + 1  # 1-indexed page number
                break
            used += len(img_bytes)
            rendered += 1
            blocks.append(
                ImageContent(
                    type="image",
                    data=base64.b64encode(img_bytes).decode(),
                    mimeType="image/jpeg",
                )
            )
        doc.close()
        if skipped_first is not None:
            last_rendered = page_indices[rendered - 1] + 1
            blocks.append(
                TextContent(
                    type="text",
                    text=(
                        f"[TRUNCATED — fit {rendered} pages into the response "
                        f"size budget. Rendered through page {last_rendered}. "
                        f"Call again with pages='{skipped_first}-...' to get "
                        f"the next pages.]"
                    ),
                )
            )
        return blocks

    # Unsupported binary (Office docs, archives, etc.) — return the file's
    # location on the user's local machine. How the agent reads it depends
    # on its host environment; this message describes the situation rather
    # than prescribing a specific tool.
    return TextContent(
        type="text",
        text=(
            f"# {filename}\n"
            f"Size: {size} bytes\n"
            f"Absolute path on the user's local machine: {filepath}\n"
            f"\n"
            f"This is a SINGLE BINARY FILE saved at the absolute path above.\n"
            f"It is NOT an extracted directory, even if the extension is an\n"
            f"Office format (.docx/.xlsx/.pptx/.odt) which is technically a\n"
            f"zip container — this server did not extract it. There are no\n"
            f"inner paths like `{filename}/word/document.xml` to read.\n"
            f"\n"
            f"DO NOT call `read_downloaded_file` on this file. That tool is\n"
            f"ONLY for paths returned by a previous zip-listing response.\n"
            f"\n"
            f"HOW TO READ IT: this file lives on the SAME machine as your\n"
            f"host agent (Claude Code, Cursor, Cline, Continue, Aider, etc.).\n"
            f"All of these ship a built-in local file-read tool — commonly\n"
            f"named `Read`, `view_file`, `read_file`, or similar — that takes\n"
            f"an absolute path and works on any file on the user's disk,\n"
            f"including files under the user's home directory. Call that\n"
            f"tool on the absolute path shown above. Office documents\n"
            f"(.docx/.xlsx/.pptx) are readable this way — the host will\n"
            f"extract their text automatically.\n"
            f"\n"
            f"Do NOT pre-emptively tell the user you 'can't access their\n"
            f"filesystem' or ask them to upload/paste the file. Try your\n"
            f"host's local file-read tool FIRST. Only if that tool actually\n"
            f"errors out should you report back to the user — and in that\n"
            f"case, include the exact error so the user can diagnose."
        ),
    )


@mcp.tool()
async def download_resource(url: str, pages: str | None = None):
    """Download a Moodle file and return its content.

    Accepts either a direct pluginfile URL OR a `/mod/resource/view.php?id=...`
    URL — redirects are followed automatically. For any module of type
    "resource" from `get_course_contents`, call this tool directly with the
    module's URL. Do NOT call `get_module_content` on resource URLs first;
    those pages 303-redirect straight to the file and will error.

    - Text files: returned as text (max 1MB, truncated if larger)
    - Images (png/jpg/gif/webp): returned inline (max 5MB)
    - PDFs: rasterized to JPEG images. Default = first 30 pages, but fewer
      may be returned to fit the host tool-result size cap — the response
      will tell you the next page to request if truncated.
      Use `pages` to select specific pages (e.g. "1-5,7,10-12").
    - Zips: extracted but NOT auto-loaded — returns a file listing instead.
      Use `read_downloaded_file` to load specific files from the zip.
    - Office docs (.docx/.xlsx/.pptx/.odt/...) and other binaries: returned
      as a text notice with the file's path on the user's local machine.
      The agent must use a host-side filesystem bridge to read it.

    Args:
        url: Moodle resource or pluginfile URL
        pages: For PDFs only. Page range like "1-5,7,10-12" (1-indexed).
    """
    import os as _os
    import zipfile

    from mcp.types import TextContent

    filepath = await download_file(url)
    filename = _os.path.basename(filepath)

    # this is because office formats are technically zip containers
    ext = _os.path.splitext(filename)[1].lower()
    is_office = ext in _OFFICE_SUFFIXES

    if not is_office and zipfile.is_zipfile(filepath):
        extract_dir = _os.path.join(
            _os.path.dirname(filepath), _os.path.splitext(filename)[0]
        )
        _os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(filepath) as zf:
            zf.extractall(extract_dir)
        _os.remove(filepath)

        listing_lines = [f"# {filename} (zip archive — choose files to load)"]
        listing_lines.append(
            "Use `read_downloaded_file(path=...)` with one of these paths:"
        )
        listing_lines.append("")
        for root, _, names in _os.walk(extract_dir):
            for name in sorted(names):
                fpath = _os.path.join(root, name)
                rel = _os.path.relpath(fpath, _os.path.dirname(filepath))
                size = _os.path.getsize(fpath)
                listing_lines.append(f"- `{rel}` ({size} bytes)")

        return [TextContent(type="text", text="\n".join(listing_lines))]

    content = _file_to_content(filepath, pages=pages)
    if isinstance(content, list):
        return content
    return [content]


@mcp.tool()
async def read_downloaded_file(path: str, pages: str | None = None):
    """Read a previously downloaded file from the local downloads directory.

    ONLY use this after `download_resource` returned a zip-listing response
    (a "zip archive — choose files to load" header with bullet-listed paths).
    Pass one of those exact listed paths verbatim — do NOT invent, modify,
    or guess paths.

    DO NOT use this tool for:
    - Office documents (.docx/.xlsx/.pptx/.odt). These were returned as a
      single binary file with an absolute path, not extracted. They have no
      inner paths like `foo.docx/word/document.xml`. Use your host
      environment's local file reader on the absolute path instead.
    - Any path not literally present in a prior zip listing.

    Args:
        path: Relative path under the downloads dir, copied verbatim from a
            zip listing returned by `download_resource`.
        pages: For PDFs only. Page range like "1-5,7" (1-indexed).
    """
    import os as _os

    from moodler_mcp.client import DOWNLOADS_DIR

    # Security: prevent path traversal
    if ".." in path or path.startswith("/"):
        raise ValueError("Invalid path")

    filepath = _os.path.join(DOWNLOADS_DIR, path)
    if not _os.path.exists(filepath):
        raise FileNotFoundError(f"Not found: {path}")

    content = _file_to_content(filepath, pages=pages)
    if isinstance(content, list):
        return content
    return [content]


@mcp.tool()
async def get_module_content(url: str) -> str:
    """Get content from a Moodle module page (assignment, folder, URL, page, etc).

    Extracts files, links, and descriptions from any Moodle module page.
    Use download_resource to download individual files from the results.

    IMPORTANT: Do NOT call this on `/mod/resource/view.php?id=...` URLs
    (modules of type "resource" from `get_course_contents`). Those pages
    303-redirect directly to the underlying file and have no HTML content
    to scrape — call `download_resource(url)` on the resource URL instead.
    This tool is for `/mod/assign/`, `/mod/folder/`, `/mod/url/`, `/mod/page/`,
    and similar wrapper pages.

    Args:
        url: Moodle module URL (e.g. '/mod/assign/view.php?id=570007')
    """
    from bs4 import BeautifulSoup
    from urllib.parse import urlparse

    if not url.startswith("http"):
        from moodler_mcp.config import MOODLE_URL as base
        url = f"{base}{url}"

    parsed = urlparse(url)
    path = parsed.path
    html = await fetch_page(f"{parsed.path}?{parsed.query}" if parsed.query else parsed.path)
    soup = BeautifulSoup(html, "html.parser")

    result: dict = {}

    title_el = soup.select_one("h2, .page-header-headings h1")
    if title_el:
        result["title"] = title_el.get_text(strip=True)

    intro = soup.select_one(".intro, .activity-description, .assignmentintro, .mod-description")
    if intro:
        result["description"] = intro.get_text(strip=True)

    files = []
    for a in soup.select("a[href*='pluginfile']"):
        name = a.get_text(strip=True)
        href = a.get("href", "")
        if name and href:
            files.append({"name": name, "url": href})
    if files:
        result["files"] = files

    if "/mod/url/" in path:
        for a in soup.select(".urlworkaround a, .resourceworkaround a"):
            result["external_url"] = a.get("href", "")
            break

    if "/mod/folder/" in path:
        folder_files = []
        for a in soup.select(".fp-filename-icon a, .foldertree a[href*='pluginfile']"):
            name = a.get_text(strip=True)
            href = a.get("href", "")
            if name and href:
                folder_files.append({"name": name, "url": href})
        if folder_files:
            result["files"] = folder_files

    if "/mod/assign/" in path:
        for row in soup.select(".submissionstatustable tr, .generaltable tr"):
            cells = row.select("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).lower()
                value = cells[1].get_text(strip=True)
                if "due" in label:
                    result["due_date"] = value
                elif "status" in label and "submission" in label:
                    result["submission_status"] = value
                elif "grading" in label and "status" in label:
                    result["grading_status"] = value
                elif "grade" in label and "status" not in label:
                    result["grade"] = value

    return json.dumps(result, indent=2)
