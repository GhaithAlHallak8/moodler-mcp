# Contributing to moodler-mcp

Thanks for wanting to contribute! This project uses a fork-and-PR workflow.

## Workflow

1. Fork the repo on GitHub.
2. Clone your fork, create a feature branch: `git checkout -b feat/my-thing`.
3. Make changes, commit, push to your fork.
4. Open a PR against `main` on the upstream repo.
5. A maintainer will squash-merge once CI passes.

## Local setup

Requires Python 3.14 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv tool install pre-commit
pre-commit install
```

Run the server locally:

```bash
uv run python -m moodler_mcp
```

First run opens a Chromium window for Moodle SSO. Set `MOODLE_URL` if your
instance differs from the default.

## Quality checks

Run the same checks CI runs:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
```

`pre-commit` runs ruff and file-hygiene hooks automatically on `git commit`.

## PR title format

Your PR title becomes the squash-merge commit message on `main`, which
[release-please](https://github.com/googleapis/release-please) parses to
determine version bumps. Use the
[Conventional Commits](https://www.conventionalcommits.org/) format:

- `feat: add new tool for X` → minor bump
- `fix: handle stale session cookie` → patch bump
- `feat!: rename MOODLE_URL env var` (or `BREAKING CHANGE:` in body) → major bump
- `docs:`, `chore:`, `ci:`, `refactor:`, `test:`, `style:`, `perf:`, `build:` → no version bump

Commits inside your fork branch do **not** need to follow this format — only the
PR title matters.

## Releases

Releases are automated. `release-please` opens a "release PR" on `main` that
accumulates changes since the last tag; merging it publishes a GitHub Release
and builds the `.mcpb` bundle as a release asset.
