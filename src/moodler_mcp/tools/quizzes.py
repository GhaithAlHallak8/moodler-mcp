from mcp.types import ToolAnnotations
from pydantic import BaseModel

from moodler_mcp import moodle_api as api
from moodler_mcp.results import iso, result, strip_html
from moodler_mcp.server import mcp

READ = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)


class Quiz(BaseModel):
    quiz_id: int
    cmid: int
    name: str
    opens: str | None
    closes: str | None
    time_limit_s: int | None
    attempts_allowed: int
    max_grade: float | None
    intro: str


class QuizList(BaseModel):
    course_id: int
    total: int
    quizzes: list[Quiz]


class Attempt(BaseModel):
    attempt_id: int
    number: int
    state: str
    started: str | None
    finished: str | None
    sum_grades: float | None


class QuizAttempts(BaseModel):
    quiz_id: int
    best_grade: str | None
    total: int
    attempts: list[Attempt]


class ReviewQuestion(BaseModel):
    slot: int
    type: str
    status: str | None
    mark: str | None
    max_mark: float | None
    text: str


class AttemptReview(BaseModel):
    attempt_id: int
    grade: str | None
    state: str | None
    questions: list[ReviewQuestion]


@mcp.tool(title="List quizzes", annotations=READ)
async def list_quizzes(course_id: int) -> QuizList:
    """Quizzes in a course with open and close times.

    Args:
        course_id: The Moodle course id
    """
    data = await api.quizzes(course_id=course_id)
    items = [
        Quiz(
            quiz_id=q["id"],
            cmid=q["coursemodule"],
            name=q.get("name", ""),
            opens=iso(q.get("timeopen")),
            closes=iso(q.get("timeclose")),
            time_limit_s=q.get("timelimit") or None,
            attempts_allowed=int(q.get("attempts") or 0),
            max_grade=q.get("grade"),
            intro=strip_html(q.get("intro")),
        )
        for q in data.get("quizzes", [])
    ]
    return result(
        f"{len(items)} quiz(zes).", QuizList(course_id=course_id, total=len(items), quizzes=items)
    )


@mcp.tool(title="Quiz attempts", annotations=READ)
async def get_quiz_attempts(quiz_id: int) -> QuizAttempts:
    """Your attempts on a quiz and your best grade.

    Args:
        quiz_id: Quiz instance id from list_quizzes
    """
    attempts = await api.quiz_attempts(quiz_id=quiz_id)
    best = await api.quiz_best_grade(quiz_id=quiz_id)
    items = [
        Attempt(
            attempt_id=a["id"],
            number=int(a.get("attempt") or 0),
            state=a.get("state", ""),
            started=iso(a.get("timestart")),
            finished=iso(a.get("timefinish")),
            sum_grades=a.get("sumgrades"),
        )
        for a in attempts.get("attempts", [])
    ]
    grade = str(best.get("grade")) if best.get("hasgrade") else None
    return result(
        f"{len(items)} attempt(s), best grade {grade or 'none'}.",
        QuizAttempts(quiz_id=quiz_id, best_grade=grade, total=len(items), attempts=items),
    )


@mcp.tool(title="Quiz attempt review", annotations=READ)
async def get_quiz_attempt_review(attempt_id: int) -> AttemptReview:
    """Review a finished quiz attempt: each question's text, your mark and status.
    Only works when the quiz allows review.

    Args:
        attempt_id: From get_quiz_attempts
    """
    data = await api.attempt_review(attempt_id=attempt_id)
    questions = [
        ReviewQuestion(
            slot=int(q.get("slot") or 0),
            type=q.get("type", ""),
            status=q.get("status"),
            mark=q.get("mark"),
            max_mark=q.get("maxmark"),
            text=strip_html(q.get("html"))[:4000],
        )
        for q in data.get("questions", [])
    ]
    attempt = data.get("attempt") or {}
    grade = data.get("grade")
    out = AttemptReview(
        attempt_id=attempt_id,
        grade=str(grade) if grade not in (None, "") else None,
        state=attempt.get("state"),
        questions=questions,
    )
    return result(f"{len(questions)} question(s), grade {out.grade or 'not graded'}.", out)
