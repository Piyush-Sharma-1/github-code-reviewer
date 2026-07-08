from typing import TypedDict
from langgraph.graph import StateGraph, END

from tools.linter_runner import run_pylint
from tools.test_runner import run_tests
from agents.reviewer_agent import summarize_findings
from agents.fixer_agent import propose_fix
from agents.summarizer_agent import generate_pr_comment
from config import MAX_FIX_ITERATIONS

from typing import Callable, Optional

# Global-ish callback used to report progress. Set per-run via run_pipeline().
_progress_callback: Optional[Callable[[str, dict], None]] = None


def _emit(event: str, data: dict = None):
    if _progress_callback:
        _progress_callback(event, data or {})

class PipelineState(TypedDict):
    filepath: str
    test_path: str
    deps_dir: Optional[str]
    original_code: str
    current_code: str
    lint_findings: list
    review_summary: str
    initial_review_summary: str
    initial_issue_count: int
    test_result: dict
    iteration_count: int
    final_status: str
    final_report: str

def build_report(filepath, review_summary, test_result, iteration_count, final_status):
    report_lines = [
        f"# Code Review Report: {filepath}",
        "",
        f"**Status:** {final_status}",
        f"**Fix iterations used:** {iteration_count} / {MAX_FIX_ITERATIONS}",
        "",
        "## Reviewer Summary",
        review_summary,
        "",
        "## Test Result",
        f"Passed: {test_result.get('passed', 'N/A')}",
        "```",
        test_result.get("output", "No test output."),
        "```",
    ]
    return "\n".join(report_lines)


def reviewer_node(state: PipelineState) -> PipelineState:
    print(f"\n[Reviewer] Linting {state['filepath']} (iteration {state['iteration_count']})...")
    findings = run_pylint(state["filepath"])
    summary = summarize_findings(state["filepath"], findings)
    print(f"[Reviewer] Found {len(findings)} issue(s).")
    _emit("reviewer_done", {"issue_count": len(findings), "iteration": state["iteration_count"]})

    # Capture the very first review pass, before any fixes — this is what
    # the final report should describe as "what was found," since later
    # passes just re-check whether fixes worked.
    if state["iteration_count"] == 0:
        state["initial_review_summary"] = summary
        state["initial_issue_count"] = len(findings)

    state["lint_findings"] = findings
    state["review_summary"] = summary
    return state


def fixer_node(state: PipelineState) -> PipelineState:
    print(f"[Fixer] Proposing fix (attempt {state['iteration_count'] + 1})...")
    _emit("fixer_start", {"attempt": state["iteration_count"] + 1})

    # If a previous attempt already ran and tests failed, feed that failure
    # output into this attempt so the Fixer knows what it broke last time.
    prior_test_failure = None
    if state["iteration_count"] > 0 and state["test_result"].get("passed") is False:
        prior_test_failure = state["test_result"].get("output")

    fixed_code = propose_fix(
        state["filepath"],
        state["current_code"],
        state["lint_findings"],
        test_failure_output=prior_test_failure,
    )
    fixed_code = propose_fix(state["filepath"], state["current_code"], state["lint_findings"])
    with open(state["filepath"], "w", encoding="utf-8") as f:
        f.write(fixed_code)
    state["current_code"] = fixed_code
    state["iteration_count"] += 1
    return state


def test_node(state: PipelineState) -> PipelineState:
    print(f"[Test Runner] Running tests at {state['test_path']}...")
    result = run_tests(state["test_path"], deps_dir=state.get("deps_dir"))
    print(f"[Test Runner] Passed: {result['passed']}")
    _emit("test_done", {"passed": result["passed"]})
    state["test_result"] = result
    return state

def route_after_lint(state: PipelineState) -> str:
    if not state["lint_findings"]:
        return "no_issues"
    if state["iteration_count"] >= MAX_FIX_ITERATIONS:
        return "max_iterations_reached"
    return "needs_fix"


def route_after_test(state: PipelineState) -> str:
    if state["test_result"]["passed"]:
        return "recheck_lint"
    if state["iteration_count"] >= MAX_FIX_ITERATIONS:
        return "max_iterations_reached"
    return "retry"


def summarizer_node(state: PipelineState) -> PipelineState:
    if state["test_result"].get("passed") is None:
        print("[Summarizer] Tests not yet run — running now for final verification...")
        state["test_result"] = run_tests(state["test_path"], deps_dir=state.get("deps_dir"))
    print("[Summarizer] Generating PR comment...")
    _emit("summarizer_start", {})
    pr_comment = generate_pr_comment(
        filepath=state["filepath"],
        review_summary=state["initial_review_summary"],
        test_result=state["test_result"],
        iteration_count=state["iteration_count"],
        final_status=state["final_status"],
        max_iterations=MAX_FIX_ITERATIONS,
    )
    # Keep the raw structured report too (useful for debugging/logs),
    # but final_report is now the polished PR-comment version.
    state["final_report"] = pr_comment
    return state

graph = StateGraph(PipelineState)

graph.add_node("reviewer", reviewer_node)
graph.add_node("fixer", fixer_node)
graph.add_node("test_runner", test_node)
graph.add_node("summarizer", summarizer_node)

graph.set_entry_point("reviewer")

graph.add_conditional_edges(
    "reviewer",
    route_after_lint,
    {
        "no_issues": "summarizer",
        "needs_fix": "fixer",
        "max_iterations_reached": "summarizer",
    }
)

graph.add_edge("fixer", "test_runner")

graph.add_conditional_edges(
    "test_runner",
    route_after_test,
    {
        "recheck_lint": "reviewer",
        "retry": "reviewer",
        "max_iterations_reached": "summarizer",
    }
)

graph.add_edge("summarizer", END)

app = graph.compile()


def run_pipeline(filepath: str, test_path: str, progress_callback: Optional[Callable[[str, dict], None]] = None, deps_dir: str = None):
    global _progress_callback
    _progress_callback = progress_callback
    with open(filepath, "r", encoding="utf-8") as f:
        original = f.read()

    initial_state: PipelineState = {
        "filepath": filepath,
        "test_path": test_path,
        "deps_dir": deps_dir,
        "original_code": original,
        "current_code": original,
        "lint_findings": [],
        "review_summary": "",
        "initial_review_summary": "",
        "initial_issue_count": 0,
        "test_result": {"passed": None, "output": ""},
        "iteration_count": 0,
        "final_status": "unknown",
        "final_report": "",
    }

    final_state = app.invoke(initial_state)

    if final_state["initial_issue_count"] == 0:
        final_state["final_status"] = "No issues found."
    elif final_state["test_result"].get("passed"):
        final_state["final_status"] = "Issues fixed and verified by tests."
    else:
        final_state["final_status"] = "Max iterations reached — issues remain."

    final_state["final_report"] = generate_pr_comment(
        filepath=final_state["filepath"],
        review_summary=final_state["initial_review_summary"],
        test_result=final_state["test_result"],
        iteration_count=final_state["iteration_count"],
        final_status=final_state["final_status"],
        max_iterations=MAX_FIX_ITERATIONS,
    )
    _progress_callback = None

    return final_state
if __name__ == "__main__":
    target_file = "demo_repo/calculator.py"
    test_path = "demo_repo"

    result = run_pipeline(target_file, test_path)

    print("\n\n========== FINAL REPORT ==========")
    print(result["final_report"])