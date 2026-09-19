import os

MOODLE_URL = os.environ.get("MOODLE_URL")
if not MOODLE_URL:
    raise RuntimeError(
        "MOODLE_URL is not set. Set it to the base URL of your Moodle instance "
        "(e.g. https://moodle.example.edu), no trailing slash."
    )
MOODLE_URL = MOODLE_URL.rstrip("/")

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
APP_USER_AGENT = f"{USER_AGENT} MoodleMobile 5.1.0"

STATE_DIR = os.path.expanduser("~/.moodler-mcp")
TOKEN_FILE = os.path.join(STATE_DIR, "token.json")
LEGACY_STATE_FILE = os.path.join(STATE_DIR, "browser_state.json")
DOWNLOADS_DIR = os.path.join(STATE_DIR, "downloads")


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


CACHE_DB = os.path.join(STATE_DIR, "cache.db")
CACHE_DISABLED = _flag("MOODLER_CACHE_DISABLED")
ALLOW_STUDENT_WRITES = _flag("MOODLER_ALLOW_STUDENT_WRITES")
ALLOW_TEACHER_GRADING = _flag("MOODLER_ALLOW_TEACHER_GRADING")

BOOTSTRAP_TIMEOUT_MS = 180_000
MOBILE_SERVICE = "moodle_mobile_app"
EMBED_LIMIT_BYTES = 700_000
EMBED_FILES = os.environ.get("MOODLER_EMBED_FILES", "local").strip().lower()
LOCAL_FILE_CLIENTS = ("claude-code", "claude code", "codex", "chatgpt")
NO_EMBED_CLIENTS = ("claude-ai",)
