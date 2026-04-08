import os

MOODLE_URL = os.environ.get("MOODLE_URL")

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

STATE_DIR = os.path.expanduser("~/.moodler-mcp")
STATE_FILE = os.path.join(STATE_DIR, "browser_state.json")
