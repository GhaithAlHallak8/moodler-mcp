import json

from bs4 import BeautifulSoup

from moodler_mcp.client import fetch_page
from moodler_mcp.server import mcp


def _cell_text(row, selector: str) -> str:
    el = row.select_one(selector)
    if not el:
        return ""

    for junk in el.select(".action-menu, .actionmenu"):
        junk.decompose()
    return el.get_text(" ", strip=True)


def _item_name(row) -> str:
    name_cell = row.select_one(".column-itemname")
    if not name_cell:
        return ""

    link = name_cell.select_one("a.gradeitemheader")
    if link:
        return link.get_text(strip=True)

    title = name_cell.select_one(".rowtitle")
    if title:
        return title.get_text(" ", strip=True)
    return name_cell.get_text(" ", strip=True)


@mcp.tool()
async def get_course_grades(course_id: int) -> str:
    """Get your grades for a course by scraping the user grade report page.

    Returns grade items with their grade, range, percentage, feedback, and
    contribution to the course total, plus the course total row.

    Args:
        course_id: The Moodle course ID
    """
    html = await fetch_page(f"/grade/report/user/index.php?id={course_id}")
    soup = BeautifulSoup(html, "html.parser")

    table = soup.select_one("table.user-grade")
    if not table:
        return json.dumps(
            {
                "course_id": course_id,
                "error": "Grade report table not found on the page.",
            },
            indent=2,
        )

    items: list[dict] = []
    course_total: dict | None = None
    current_category: str | None = None
    parse_error: str | None = None

    try:
        for row in table.select("tbody > tr"):
            classes = row.get("class", [])
            if "spacer" in classes:
                continue

            category_th = row.select_one("th.category")
            if category_th and not row.select_one(".column-grade"):
                current_category = category_th.get_text(" ", strip=True)
                continue

            name = _item_name(row)
            if not name:
                continue

            entry = {
                "name": name,
                "weight": _cell_text(row, ".column-weight") or None,
                "grade": _cell_text(row, ".column-grade") or None,
                "range": _cell_text(row, ".column-range") or None,
                "percentage": _cell_text(row, ".column-percentage") or None,
                "feedback": _cell_text(row, ".column-feedback") or None,
                "contribution": _cell_text(
                    row, ".column-contributiontocoursetotal"
                ) or None,
            }

            is_total = (
                "lastrow" in classes
                or "Course total" in name
                or row.select_one(".column-itemname .aggregation") is not None
            )
            if is_total:
                course_total = entry
                continue

            if current_category:
                entry["category"] = current_category
            items.append(entry)
    except Exception as e:
        parse_error = f"{type(e).__name__}: {e}"

    result: dict = {
        "course_id": course_id,
        "items": items,
        "course_total": course_total,
    }

    # Fallback: return the raw table HTML if parsing errored OR found nothing
    # useful, so the agent can read it directly.
    if parse_error or (not items and course_total is None):
        result["raw_html"] = str(table)
        if parse_error:
            result["parse_error"] = parse_error

    return json.dumps(result, indent=2)
