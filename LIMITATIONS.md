\# Known Limitations



This project works reliably for the case it was designed and tested against — small, dependency-free (or dependency-declared) Python files with a discoverable sibling test file, where issues are mechanical (unused imports, missing docstrings, simple style problems). Outside that case, the following limitations apply.



\## 1. The Fixer's whole-file regeneration is unstable on non-trivial fixes



\*\*What happens:\*\* on each retry, the Fixer is given the full file content and asked to return the \*entire corrected file\*, rather than a targeted patch. This means every retry is an independent, full regeneration — not an incremental edit.



\*\*Observed evidence:\*\* tested against a small (15-line) file with two simple functions and one external dependency (`requests`). The original code was already correct. Across 2 fix attempts:



\- Attempt 1: lint findings went from 5 → 10 after the "fix"

\- Attempt 2: lint findings went from 10 → 17 after the "fix"

\- Tests failed after both attempts, despite the original code working correctly before any fix was applied



Feeding the actual test failure output back into the next attempt (a retry-feedback mechanism) did not resolve this — the Fixer still diverged rather than converging.



\*\*Why this happens:\*\* the Fixer has no semantic understanding of \*why\* tests failed, only what pylint flagged. It optimizes purely for "satisfy the linter," with each full-file rewrite introducing a chance to alter working logic — and that risk compounds with file size and fix count, since every regenerated line is a fresh opportunity for drift from the original behavior.



\*\*What would fix this:\*\* a diff-based Fixer — one that proposes a minimal, targeted patch (e.g., specific line changes) rather than a full-file rewrite. Minimal patches are both easier for an LLM to get right and easier to mechanically verify (e.g., confirming only the intended lines changed) before applying. This is a genuine architectural change, not a prompt tweak, and was intentionally scoped out of this version.



\## 2. No dependency handling beyond `requirements.txt` + pip



\- Only a root-level `requirements.txt` is detected and installed

\- No support for `pyproject.toml`, `Pipfile`, `poetry.lock`, or `setup.py`-declared dependencies

\- No handling of system-level dependencies (e.g., packages requiring compiled C extensions or OS-level libraries)



\## 3. Test discovery is heuristic, not authoritative



Test files are identified by naming convention (`test\_\*.py`, `\*\_test.py`, or anything under a `tests/` folder). Projects using `conftest.py`-only fixtures, custom `pytest.ini`/`pyproject.toml` test paths, or non-standard layouts may not have their real tests discovered correctly.



\## 4. No cross-file import resolution



Only the changed file(s) and discovered test file(s) are fetched — not the full repository. If the changed file imports from sibling modules elsewhere in the repo (common in any project with more than a couple of files), those imports will fail before the Fixer or Test Runner ever get a meaningful signal.



\## 5. Multi-file PRs are capped, not intelligently handled



PRs changing more than 5 Python files are rejected outright as a safety/cost measure. PRs at or under that limit are processed file-by-file, independently — there's no cross-file awareness (e.g., a fix in one file that depends on a corresponding change in another).



\## 6. Large files aren't chunked



The entire file content is sent to the LLM in a single prompt. Very large files risk exceeding what the model can track accurately in one pass; there's no chunking or partial-context strategy.



\## 7. Review depth is limited to what pylint catches



The Reviewer only surfaces what `pylint` flags — style, unused imports, missing docstrings, and similar static patterns. It has no mechanism for detecting logic bugs that don't happen to overlap with a lint-flagged construct. (One real bug in early testing was fixed only because it happened to be embedded in a lint-flagged `if/else` block that got simplified as a side effect — not because the system understood the bug.)



\## 8. Operational constraints



\- \*\*Cold starts:\*\* free-tier hosting spins down after \~15 minutes idle; the first request afterward can take 30–60 seconds

\- \*\*Soft rate limiting:\*\* per-IP limits (5 reviews / 10 minutes) are easily bypassed by a motivated user (VPN, multiple sessions)

\- \*\*Shared fetch token:\*\* the server's own GitHub token is used for all \*fetch\* operations across all visitors, and could be rate-limited under heavy concurrent use (posting comments correctly uses each visitor's own token, and is not affected by this)



\---



\## What this demonstrates



The system reliably solves the case it targets: small-scope, lint-driven fixes verified by real test execution, with a working retry loop, live progress streaming, and end-to-end GitHub integration (fetch → fix → verify → report → post) using per-user OAuth. The limitations above are the result of deliberate, tested investigation — not unexamined gaps — and each has a clear, identified path to being addressed in a future iteration.

