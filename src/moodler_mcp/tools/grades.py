from mcp.types import ToolAnnotations
from pydantic import BaseModel

from moodler_mcp import moodle_api as api
from moodler_mcp.results import result, strip_html
from moodler_mcp.server import mcp

READ = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)


class GradeRow(BaseModel):
    item: str
    grade: str
    range: str
    percentage: str
    weight: str
    feedback: str
    contribution: str
    is_category: bool


class GradeReport(BaseModel):
    course_id: int
    user_id: int
    rows: list[GradeRow]
    course_total: str | None


def _cell(row: dict, key: str) -> str:
    cell = row.get(key)
    if not isinstance(cell, dict):
        return ""
    return strip_html(cell.get("content"))


@mcp.tool(title="Course grades", annotations=READ)
async def get_course_grades(course_id: int) -> GradeReport:
    """Your grade report for one course: every graded item with grade, range, weight,
    percentage and feedback, plus the course total.

    Args:
        course_id: The Moodle course id
    """
    user_id = await api.current_user_id()
    data = await api.grades_table(course_id=course_id, user_id=user_id)
    rows: list[GradeRow] = []
    total: str | None = None
    for table in data.get("tables", []):
        for raw in table.get("tabledata", []):
            if not isinstance(raw, dict) or not raw.get("itemname"):
                continue
            item_cell = raw.get("itemname") or {}
            row = GradeRow(
                item=strip_html(item_cell.get("content")),
                grade=_cell(raw, "grade"),
                range=_cell(raw, "range"),
                percentage=_cell(raw, "percentage"),
                weight=_cell(raw, "weight"),
                feedback=_cell(raw, "feedback"),
                contribution=_cell(raw, "contributiontocoursetotal"),
                is_category="category" in str(item_cell.get("class", "")),
            )
            if "course total" in row.item.lower():
                total = row.grade or None
            rows.append(row)
    return result(
        f"{len(rows)} grade row(s); course total {total or 'not available'}.",
        GradeReport(course_id=course_id, user_id=user_id, rows=rows, course_total=total),
    )


class CourseGrade(BaseModel):
    course_id: int
    grade: str
    raw_grade: str | None
    rank: int | None


class GradeOverview(BaseModel):
    total: int
    grades: list[CourseGrade]


class GradeItem(BaseModel):
    id: str
    name: str
    category: str | None


class GradeItemList(BaseModel):
    course_id: int
    total: int
    items: list[GradeItem]


@mcp.tool(title="Grade overview", annotations=READ)
async def get_grade_overview() -> GradeOverview:
    """Your final grade in every enrolled course, one call."""
    data = await api.grade_overview()
    grades = [
        CourseGrade(
            course_id=g["courseid"],
            grade=strip_html(str(g.get("grade", ""))),
            raw_grade=g.get("rawgrade"),
            rank=g.get("rank"),
        )
        for g in data.get("grades", [])
    ]
    return result(
        f"Grades for {len(grades)} course(s).", GradeOverview(total=len(grades), grades=grades)
    )


@mcp.tool(title="Grade items", annotations=READ)
async def get_grade_items(course_id: int) -> GradeItemList:
    """Teacher view: the gradebook items defined in a course.

    Args:
        course_id: The Moodle course id
    """
    data = await api.grade_items(course_id=course_id)
    items = [
        GradeItem(
            id=str(i.get("id")), name=strip_html(i.get("itemname")), category=i.get("category")
        )
        for i in data.get("gradeItems", [])
    ]
    return result(
        f"{len(items)} grade item(s).",
        GradeItemList(course_id=course_id, total=len(items), items=items),
    )
