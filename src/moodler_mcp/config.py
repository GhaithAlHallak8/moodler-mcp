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

STATE_DIR = os.path.expanduser("~/.moodler-mcp")
STATE_FILE = os.path.join(STATE_DIR, "browser_state.json")

# Cache
CACHE_DB = os.path.join(STATE_DIR, "cache.db")
CACHE_DISABLED = bool(os.environ.get("MOODLER_CACHE_DISABLED"))
