# Future Work

This project currently handles its core scenario well: small Python files with a discoverable test file, where issues are mechanical (unused imports, missing docstrings, style problems, simple logic bugs) and dependencies are declared in a standard requirements.txt. Given more time, here's what I would extend next, in priority order.

## 1. Diff-based fixing instead of whole-file regeneration

Current approach: the Fixer is given the full file content and the linter's findings, and asked to return a corrected version of the entire file.

What I'd build next: a Fixer that proposes a minimal, targeted patch (specific line changes) instead of regenerating the whole file. This would make each fix easier to verify mechanically (confirm only the intended lines changed) and reduce the chance of unrelated drift creeping in across retries — especially valuable on larger files or multi-issue fixes, where a full rewrite has more surface area to get something subtly wrong.

Testing note: in testing against a small file with a real dependency, I observed the whole-file approach occasionally increase lint findings across retries rather than converge — a good concrete case study for why the diff-based approach would be the next architectural investment, and something I'd like to explore further with more time.

## 2. Broader dependency management

Currently only a root-level requirements.txt is detected and installed via pip. With more time, I'd add support for pyproject.toml, Pipfile/poetry.lock, and potentially basic handling of system-level dependencies for packages that need compiled extensions.

## 3. Smarter test discovery

Right now tests are found by naming convention (test_*.py, *_test.py, or a tests/ folder). A more robust version would respect pytest.ini/pyproject.toml configured test paths and understand conftest.py-based fixture setups, so test discovery works reliably across more varied project layouts.

## 4. Fetching full repository context, not just changed files

Right now only the changed file(s) and discovered test file(s) are pulled from the PR. For files that import from sibling modules elsewhere in the repo, fetching the full relevant package tree (not just the diff) would let the pipeline handle realistically interconnected codebases rather than isolated single files.

## 5. Smarter handling of larger, multi-file PRs

Currently capped at 5 changed files per review as a safety/cost measure, and each file is processed independently. A future version could add cross-file awareness — for example, recognizing when a fix in one file depends on a corresponding change in another — and chunk very large files intelligently instead of sending full content in a single LLM call.

## 6. Deeper static analysis beyond pylint

The Reviewer currently surfaces what pylint catches — style and structural patterns. Adding a complementary analysis pass (for example, type checking with mypy, or a dedicated LLM pass focused specifically on reasoning about behavioral correctness rather than style) would give the system a better chance at catching logic issues that don't happen to overlap with a lint-flagged construct.

## 7. Production-grade operational hardening

With more infrastructure time, I'd move to always-on hosting (removing cold-start delays), add authenticated per-user rate limiting instead of per-IP, and give each visitor's fetch operations their own token budget rather than sharing the server's GitHub token across all traffic.

---

These are all natural next steps rather than blockers — the current system already demonstrates the full loop end-to-end (fetch, review, fix, verify, report, post, with live progress and per-user GitHub OAuth), and each item above extends that foundation rather than replacing it.
