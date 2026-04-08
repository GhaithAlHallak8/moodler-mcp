# moodler-mcp

A Python MCP server for interacting with Moodle LMS via AI assistants.

## Setup

```bash
uv sync
cp .env.example .env
# Edit .env with your Moodle URL and API token
```

## Usage

```bash
MOODLE_API_URL=https://your-moodle.com/webservice/rest/server.php \
MOODLE_API_TOKEN=your_token \
uv run python -m moodler_mcp
```

### Claude Desktop config

```json
{
  "mcpServers": {
    "moodler-mcp": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/moodler-mcp", "run", "python", "-m", "moodler_mcp"],
      "env": {
        "MOODLE_API_URL": "https://your-moodle.com/webservice/rest/server.php",
        "MOODLE_API_TOKEN": "your_token"
      }
    }
  }
}
```

## Tools

| Tool | Description |
|------|-------------|
| `list_courses` | List available courses with pagination |
| `search_courses` | Search courses by name/description |
| `get_course` | Get details for a specific course |
| `get_course_contents` | Get sections, activities, and resources in a course |
| `get_enrolled_users` | Get users enrolled in a course (filterable by role) |
| `get_assignments` | Get all assignments in a course |
| `get_submissions` | Get submissions for an assignment |
| `get_submission_content` | Get full submission content (text + files) |
| `provide_feedback` | Grade and comment on a submission |
| `get_quizzes` | Get all quizzes in a course |
| `get_quiz_best_grade` | Get a student's best quiz grade |
| `get_user_grades` | Get full gradebook for a student in a course |
