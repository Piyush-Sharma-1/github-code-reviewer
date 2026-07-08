# AI PR Reviewer

An autonomous code review agent that fetches a real GitHub pull request, lints and reviews the changed code, proposes and applies a fix, verifies the fix by actually running the test suite, and reports back — either as a live-streamed web experience or as a posted comment on the PR itself.

**Live demo:** https://github-code-reviewer-6adl.onrender.com

(This is on Render's free tier, so the first request after about 15 minutes of inactivity can take 30–60 seconds to wake up.)

## What it does

1. **Fetches** a PR's changed files directly from the GitHub API — title, branch, diffs, full file content
2. **Reviews** the code with pylint, then summarizes the findings in plain English via an LLM (Groq / Llama 3.3 70B)
3. **Fixes** the flagged issues automatically — the LLM proposes a corrected version of the file
4. **Verifies** the fix by actually running pytest in a sandboxed subprocess, rather than just trusting the LLM
5. **Retries** up to 3 times if tests fail, feeding the actual test failure output back into the next attempt
6. **Summarizes** the whole cycle into a polished, markdown-formatted report
7. **Posts** that report back to the real PR as a GitHub comment, using the logged-in user's own OAuth token, never a shared server credential

All of this is orchestrated as a multi-agent graph using LangGraph, with a live-streaming FastAPI + WebSocket backend and a lightweight vanilla HTML/CSS/JS frontend (no build step required).

## Architecture

```
Browser (frontend.html)
        |
        |  WebSocket (live progress)  +  REST (post comment)
        v
FastAPI backend (backend.py)
        |
        |-- GitHub Fetcher        -> pulls PR metadata, changed files, full file content, repo tree
        |-- Dependency Installer  -> installs requirements.txt into an isolated folder, if present
        |
        v
LangGraph pipeline (pipeline.py)
        |
        |-- Reviewer    -> pylint findings + LLM plain-English summary
        |-- Fixer       -> LLM proposes a corrected file, given findings (+ prior test failure, on retry)
        |-- Test Runner -> sandboxed pytest run (stripped env, resource limits, timeout)
        |-- Summarizer  -> LLM writes the final PR-comment-style report
        |
        v
GitHub API -> posts the report as a real PR comment, using the visitor's own OAuth token
```

## Features

- Live progress streaming — watch each agent step happen in real time via WebSocket, not just a final result
- GitHub OAuth login — any visitor can log in with their own GitHub account; comments are posted with their token, never the server's
- Sandboxed test execution — stripped environment variables (no leaked API keys), resource limits, timeouts, workdir isolation
- XSS-safe rendering — all PR-derived content (titles, filenames, LLM output) is HTML-escaped before display
- Rate limiting — per-IP request caps on both the REST and WebSocket review endpoints
- Dependency installation — automatically installs a PR's requirements.txt into an isolated folder before running its tests
- Path-traversal guarded file writes — rejects any file path that would escape the sandboxed working directory

## Tech stack

- Orchestration: LangGraph
- LLM: Groq (Llama 3.3 70B) via langchain-groq
- Backend: FastAPI, WebSockets, Uvicorn
- Linting: pylint
- Testing: pytest
- Auth: GitHub OAuth (Authorization Code flow)
- Frontend: Vanilla HTML/CSS/JS (no framework, no build step)
- Hosting: Render (free tier)

## Local setup

```
git clone https://github.com/Piyush-Sharma-1/github-code-reviewer.git
cd github-code-reviewer
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_groq_key
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_CLIENT_ID=your_oauth_app_client_id
GITHUB_CLIENT_SECRET=your_oauth_app_client_secret
```

Run it:

```
uvicorn backend:app
```

Then visit http://127.0.0.1:8000.

## Known limitations

This project is transparent about where it works well and where it doesn't. See LIMITATIONS.md for the full breakdown, including a concrete example of the Fixer's whole-file-regeneration approach failing to converge on a real test case, and what a more robust, diff-based redesign would look like.

## Project structure

```
agents/
  reviewer_agent.py     - pylint + LLM summary
  fixer_agent.py         - LLM proposes corrected file
  summarizer_agent.py    - LLM writes final PR comment
tools/
  github_fetcher.py      - GitHub API: fetch PR, files, post comments
  linter_runner.py        - pylint wrapper
  test_runner.py           - sandboxed pytest runner + dependency installer
pipeline.py                - LangGraph orchestration + retry loop
backend.py                 - FastAPI app: REST + WebSocket + OAuth
frontend.html               - live progress UI
demo_repo/                  - seeded bug + tests for local testing
run_on_pr.py                - standalone CLI script: fetch, review, fix, test, post
config.py                   - environment variable loading
```

## Security notes

- Secrets (.env) are never committed — see .gitignore
- CORS is restricted to the app's own origin
- The server's own GitHub token is used only for fetching public data; posting comments always uses the visitor's own OAuth token
- Untrusted content (PR titles, file names, LLM-generated report text) is HTML-escaped before rendering
- Test execution runs with a stripped environment (no leaked secrets), resource limits, and a hard timeout
