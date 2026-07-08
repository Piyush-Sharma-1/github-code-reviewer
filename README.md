\# AI PR Reviewer



An autonomous code review agent that fetches a real GitHub Pull Request, lints and reviews the changed code, proposes and applies a fix, verifies the fix by actually running the test suite, and reports back — either as a live-streamed web experience or as a posted comment on the PR itself.



\*\*Live demo:\*\* https://github-code-reviewer-6adl.onrender.com

\*(Free-tier hosting — the first request after \~15 minutes of inactivity may take 30–60s to wake up.)\*



\---



\## What it does



1\. \*\*Fetches\*\* a PR's changed files directly from the GitHub API (title, branch, diffs, full file content)

2\. \*\*Reviews\*\* the code with `pylint`, then summarizes the findings in plain English via an LLM (Groq / Llama 3.3 70B)

3\. \*\*Fixes\*\* the flagged issues automatically — the LLM proposes a corrected version of the file

4\. \*\*Verifies\*\* the fix by actually running `pytest` in a sandboxed subprocess, not just trusting the LLM

5\. \*\*Retries\*\* up to 3 times if tests fail, feeding the actual test failure output back into the next attempt

6\. \*\*Summarizes\*\* the whole cycle into a polished, Markdown-formatted report

7\. \*\*Posts\*\* that report back to the real PR as a GitHub comment — using the logged-in user's own OAuth token, never a shared server credential



All of this is orchestrated as a multi-agent graph using \*\*LangGraph\*\*, with a live-streaming \*\*FastAPI + WebSocket\*\* backend and a lightweight vanilla HTML/CSS/JS frontend (no build step required).



\---



\## Architecture

Browser (frontend.html)

│  WebSocket (live progress) + REST (post comment)

▼

FastAPI backend (backend.py)

│

├─ GitHub Fetcher  → pulls PR metadata, changed files, full file content, repo tree

├─ Dependency Installer → installs requirements.txt into an isolated folder, if present

│

▼

LangGraph pipeline (pipeline.py)

│

├─ Reviewer  → pylint findings + LLM plain-English summary

├─ Fixer     → LLM proposes a corrected file, given findings (+ prior test failure, on retry)

├─ Test Runner → sandboxed pytest run (stripped env, resource limits, timeout)

└─ Summarizer → LLM writes the final PR-comment-style report

│

▼

GitHub API → posts the report as a real PR comment, using the visitor's own OAuth token

\---



\## Features



\- \*\*Live progress streaming\*\* — watch each agent step happen in real time via WebSocket, not just a final result

\- \*\*GitHub OAuth login\*\* — any visitor can log in with their own GitHub account; comments are posted with \*their\* token, never the server's

\- \*\*Sandboxed test execution\*\* — stripped environment variables (no leaked API keys), resource limits, timeouts, workdir isolation

\- \*\*XSS-safe rendering\*\* — all PR-derived content (titles, filenames, LLM output) is HTML-escaped before display

\- \*\*Rate limiting\*\* — per-IP request caps on both the REST and WebSocket review endpoints

\- \*\*Dependency installation\*\* — automatically installs a PR's `requirements.txt` into an isolated folder before running its tests

\- \*\*Path-traversal guarded file writes\*\* — rejects any file path that would escape the sandboxed working directory



\---



\## Tech stack



| Layer | Tool |

|---|---|

| Orchestration | LangGraph |

| LLM | Groq (Llama 3.3 70B) via `langchain-groq` |

| Backend | FastAPI, WebSockets, Uvicorn |

| Linting | pylint |

| Testing | pytest |

| Auth | GitHub OAuth (Authorization Code flow) |

| Frontend | Vanilla HTML/CSS/JS (no framework, no build step) |

| Hosting | Render (free tier) |



\---



\## Local setup



```powershell

git clone https://github.com/Piyush-Sharma-1/github-code-reviewer.git

cd github-code-reviewer

python -m venv venv

venv\\Scripts\\activate

pip install -r requirements.txt

```



Create a `.env` file in the project root:

GROQ\_API\_KEY=your\_groq\_key

GITHUB\_TOKEN=your\_github\_personal\_access\_token

GITHUB\_CLIENT\_ID=your\_oauth\_app\_client\_id

GITHUB\_CLIENT\_SECRET=your\_oauth\_app\_client\_secret

Run it:



```powershell

uvicorn backend:app

```



Visit `http://127.0.0.1:8000`.



\---



\## Known limitations



This project is transparent about where it works well and where it doesn't — see \[LIMITATIONS.md](./LIMITATIONS.md) for the full breakdown, including a concrete example of the Fixer's whole-file-regeneration approach failing to converge on a real test case, and what a more robust (diff-based) redesign would look like.



\---



\## Project structure

├── agents/

│   ├── reviewer\_agent.py     # pylint + LLM summary

│   ├── fixer\_agent.py        # LLM proposes corrected file

│   └── summarizer\_agent.py   # LLM writes final PR comment

├── tools/

│   ├── github\_fetcher.py     # GitHub API: fetch PR, files, post comments

│   ├── linter\_runner.py      # pylint wrapper

│   └── test\_runner.py        # sandboxed pytest runner + dependency installer

├── pipeline.py                # LangGraph orchestration + retry loop

├── backend.py                 # FastAPI app: REST + WebSocket + OAuth

├── frontend.html              # Live progress UI

├── demo\_repo/                 # Seeded bug + tests for local testing

├── run\_on\_pr.py                # Standalone CLI script: fetch → review → fix → test → post

└── config.py                   # Environment variable loading

\---



\## Security notes



\- Secrets (`.env`) are never committed — see `.gitignore`

\- CORS is restricted to the app's own origin

\- The server's own GitHub token is used only for \*fetching\* public data; \*posting\* comments always uses the visitor's own OAuth token

\- Untrusted content (PR titles, file names, LLM-generated report text) is HTML-escaped before rendering

\- Test execution runs with a stripped environment (no leaked secrets), resource limits, and a hard timeout



