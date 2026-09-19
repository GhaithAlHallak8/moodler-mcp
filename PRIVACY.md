# Privacy Policy

_Last updated: 2026-09-19_

moodler-mcp is a local tool that connects your AI assistant to **your own
Moodle instance**. It runs entirely on your machine. It does **not** send your
data to any third party, and it has no telemetry, analytics, or remote
reporting of any kind.

## What the tool accesses

When you use moodler-mcp, it connects to the Moodle URL you configure
(`MOODLE_URL`) and retrieves data you already have access to as a logged-in
Moodle user — your courses, assignments, deadlines, grades, feedback, and
resource files. It does this by:

1. Launching a browser window once, when you run the `login_to_moodle` tool,
   so you can complete single-sign-on (SSO) against your institution's
   identity provider.
2. Asking Moodle for a web service token for your account (the same kind the
   official Moodle mobile app receives) and storing it locally.
3. Making requests to your Moodle instance's REST web service on your behalf
   with that token, and downloading files you ask for.

## What is stored locally

All state lives under `~/.moodler-mcp/` on your machine:

- `token.json` — your Moodle web service token and private token, readable
  only by your user account. You can revoke the token at any time from
  Moodle's Security keys page.
- `cache.db` — a local SQLite cache of Moodle API responses (course lists,
  section contents, grade reports, etc.) used to make repeated tool calls
  instant. See the cache TTL documentation in the project README.
- `downloads/` — files you explicitly download through the
  `download_resource` tool (PDFs, slides, etc.).

You can wipe everything by deleting the `~/.moodler-mcp/` directory.

## What is sent where

- **To your Moodle instance**: REST web service requests carrying your
  token, over HTTPS. No more, no less.
- **To your AI assistant (e.g. Claude Desktop)**: the tool results that the
  assistant asked for, exactly as you would see them yourself. Whatever
  privacy policy your AI assistant has applies to how that data is processed
  once it leaves moodler-mcp.
- **To anyone else**: nothing. moodler-mcp has no outbound connections other
  than to your Moodle instance.

## What is never collected

- No usage analytics, crash reports, or telemetry.
- No account credentials are stored — moodler-mcp never sees your password;
  SSO happens in the browser window and only the resulting token is retained.
- No data is transmitted to the project author or any hosted service.

## Your responsibilities

moodler-mcp runs with the same access level your Moodle account has. Treat
the contents of `~/.moodler-mcp/` as sensitive — anyone with access to that
directory can act as you against your Moodle instance until you revoke the
token.

## Questions

Open an issue at <https://github.com/GhaithAlHallak8/moodler-mcp/issues>.
