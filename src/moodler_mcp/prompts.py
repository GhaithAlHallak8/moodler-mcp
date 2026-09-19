from moodler_mcp.server import mcp


@mcp.prompt(title="What is due")
def whats_due() -> str:
    """Summarise everything due in the next two weeks across all courses."""
    return (
        "Call get_upcoming_deadlines with limit 30 and get_notifications with unread_only true. "
        "Group the deadlines by day, flag anything overdue, and list unread notifications that "
        "mention grades or due dates."
    )


@mcp.prompt(title="Course status")
def course_status(course_id: int) -> str:
    """Where do I stand in one course."""
    return (
        f"For course {course_id}: call list_assignments, get_course_grades, "
        "get_completion_status and get_course_deadlines. Report submitted versus missing "
        "assignments, current grades, incomplete activities and the next three deadlines."
    )


@mcp.prompt(title="Review feedback")
def review_feedback(course_id: int) -> str:
    """Collect all teacher feedback in a course."""
    return (
        f"Call list_assignments for course {course_id}, then get_assignment_feedback for every "
        "assignment with a cmid. Summarise the grade and feedback per assignment and point out "
        "recurring comments."
    )


@mcp.prompt(title="Grading queue")
def grading_queue(course_id: int) -> str:
    """Teacher: what needs grading in a course."""
    return (
        f"Call list_assignments for course {course_id}, then get_grading_summary for each "
        "assign_id. List assignments with submissions needing grading, most urgent by due date first."
    )
