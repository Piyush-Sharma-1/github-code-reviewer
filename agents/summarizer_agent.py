from langchain_groq import ChatGroq
from config import GROQ_API_KEY, LLM_MODEL

llm = ChatGroq(model=LLM_MODEL, api_key=GROQ_API_KEY, temperature=0)


def generate_pr_comment(filepath: str, review_summary: str, test_result: dict,
                         iteration_count: int, final_status: str, max_iterations: int) -> str:
    """
    Uses the LLM to write a polished, PR-comment-style summary of the
    whole review/fix/test cycle for a single file.
    """
    test_passed = test_result.get("passed")
    test_output_tail = test_result.get("output", "")[-800:]  # keep it short

    prompt = f"""You are an automated code review bot writing a comment on a GitHub Pull Request.

Below is data from an automated review pipeline that ran on the file `{filepath}`:

- Final status: {final_status}
- Fix iterations used: {iteration_count} / {max_iterations}
- Tests passed: {test_passed}
- Reviewer's findings summary:
{review_summary}

- Test output (tail):
{test_output_tail}

Write a PR comment that:
1. Starts with a short, friendly one-line summary (e.g. "I reviewed this file and found a few small issues, which I fixed automatically.")
2. Lists what was found and fixed, in plain English bullet points.
3. States clearly whether tests passed after the fix.
4. If iterations were used, mention it briefly (e.g. "It took 2 attempts to get everything passing.").
5. Keep it under 150 words, professional but warm tone, like a helpful senior engineer.
6. Format using Markdown (headers, bullets) suitable for pasting directly as a GitHub PR comment.
7. Do NOT invent findings that aren't in the data above.
"""

    response = llm.invoke(prompt)
    return response.content.strip()


if __name__ == "__main__":
    # Quick manual test with fake data resembling a real pipeline run
    fake_review_summary = (
        "- Unused imports: `os` and `sys` were imported but never used.\n"
        "- Unused variable: `x` was assigned but never used.\n"
        "- Missing docstrings: module and function docstrings were missing."
    )
    fake_test_result = {
        "passed": True,
        "output": "2 passed in 0.02s"
    }

    comment = generate_pr_comment(
        filepath="calc.py",
        review_summary=fake_review_summary,
        test_result=fake_test_result,
        iteration_count=1,
        final_status="Issues fixed and verified by tests.",
        max_iterations=3
    )

    print("=== GENERATED PR COMMENT ===")
    print(comment)