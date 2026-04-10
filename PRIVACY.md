# Privacy Policy

_Last updated: 2026-04-11_

moodler-mcp is a local tool that connects your AI assistant to **your own
Moodle instance**. It runs entirely on your machine. It does **not** send your
data to any third party, and it has no telemetry, analytics, or remote
reporting of any kind.

## What the tool accesses

When you use moodler-mcp, it connects to the Moodle URL you configure
(`MOODLE_URL`) and retrieves data you already have access to as a logged-in
Moodle user — your courses, assignments, deadlines, grades, feedback, and
resource files. It does this by:

1. Launching a Chromium browser window on first run so you can complete
   single-sign-on (SSO) against your institution's identity provider.
2. Storing the resulting session cookie locally so subsequent runs can reuse
   your authenticated session without re-prompting you.
3. Making HTTP requests to your Moodle instance's internal endpoints on your
   behalf, using the same session a web browser would.

## What is stored locally

All state lives under `~/.moodler-mcp/` on your machine:

- `browser_state.json` — your Moodle session cookie and browser storage,
  created by Playwright after SSO. This is the same kind of data your web
  browser stores when you stay logged into Moodle.
- `cache.db` — a local SQLite cache of Moodle API responses (course lists,
  section contents, grade reports, etc.) used to make repeated tool calls
  instant. See the cache TTL documentation in the project README.
- `downloads/` — files you explicitly download through the
  `download_resource` tool (PDFs, slides, etc.).

You can wipe everything by deleting the `~/.moodler-mcp/` directory.

## What is sent where

- **To your Moodle instance**: the same HTTP requests a logged-in browser
  would make. No more, no less.
- **To your AI assistant (e.g. Claude Desktop)**: the tool results that the
  assistant asked for, exactly as you would see them yourself. Whatever
  privacy policy your AI assistant has applies to how that data is processed
  once it leaves moodler-mcp.
- **To anyone else**: nothing. moodler-mcp has no outbound connections other
  than to your Moodle instance.

## What is never collected

- No usage analytics, crash reports, or telemetry.
- No account credentials are stored — moodler-mcp never sees your password;
  SSO happens in the browser window and only the resulting cookie is retained.
- No data is transmitted to the project author or any hosted service.

## Your responsibilities

moodler-mcp runs with the same access level your Moodle account has. Treat
the contents of `~/.moodler-mcp/` as sensitive — anyone with access to that
directory can act as you against your Moodle instance until the session
expires.

## Questions

Open an issue at <https://github.com/GhaithAlHallak8/moodler-mcp/issues>.
