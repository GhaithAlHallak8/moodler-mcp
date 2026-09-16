from pathlib import Path
from urllib.parse import unquote

from mcp.server.mcpserver import MCPServer

from moodler_mcp.config import STATE_DIR

mcp = MCPServer("moodler-mcp")

DOWNLOADS_DIR = Path(STATE_DIR) / "downloads"


@mcp.resource("downloads:///{filename}")
def read_download(filename: str) -> str | bytes:
    """Read a previously downloaded Moodle file by name."""
    filename = unquote(filename)
    if ".." in filename or filename.startswith("/"):
        raise ValueError("Invalid filename")

    filepath = DOWNLOADS_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filename}")

    text_suffixes = {
        ".py",
        ".txt",
        ".csv",
        ".json",
        ".ipynb",
        ".md",
        ".html",
        ".htm",
        ".xml",
        ".yaml",
        ".yml",
        ".java",
        ".c",
        ".cpp",
        ".js",
        ".ts",
        ".css",
        ".sql",
        ".r",
        ".tex",
        ".ini",
        ".cfg",
        ".toml",
        ".sh",
        ".bat",
    }
    if filepath.suffix.lower() in text_suffixes:
        return filepath.read_text(errors="replace")
    return filepath.read_bytes()


# Register all tools by importing the modules
import moodler_mcp.tools.assignments  # noqa: F401, E402
import moodler_mcp.tools.auth  # noqa: F401, E402
import moodler_mcp.tools.cache  # noqa: F401, E402
import moodler_mcp.tools.calendar  # noqa: F401, E402
import moodler_mcp.tools.courses  # noqa: F401, E402
import moodler_mcp.tools.forums  # noqa: F401, E402
import moodler_mcp.tools.grades  # noqa: F401, E402
import moodler_mcp.tools.messaging  # noqa: F401, E402
import moodler_mcp.tools.quizzes  # noqa: F401, E402
import moodler_mcp.tools.students  # noqa: F401, E402
