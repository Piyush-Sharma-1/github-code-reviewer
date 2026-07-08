from langchain_groq import ChatGroq
from config import GROQ_API_KEY, LLM_MODEL
from tools.linter_runner import run_pylint

llm = ChatGroq(model=LLM_MODEL, api_key=GROQ_API_KEY, temperature=0)


def summarize_findings(filename: str, findings: list) -> str:
    """
    Takes raw linter findings and asks the LLM to summarize them
    in plain English, ranked by severity/importance.
    """
    if not findings:
        return f"No issues found in {filename}."

    findings_text = "\n".join(
        f"- Line {f.get('line', '?')}: {f.get('message', '')} ({f.get('symbol', f.get('error', 'unknown'))})"
        for f in findings
    )

    prompt = f"""You are a code reviewer. Below are raw linter findings for the file `{filename}`.

{findings_text}

Summarize these findings for a developer in plain English:
1. Rank them from most to least important (bugs > security > style).
2. Group similar issues together.
3. Keep it concise — a few bullet points, not a wall of text.
4. Do not invent issues that aren't in the list above.
"""

    response = llm.invoke(prompt)
    return response.content


def review_file(filepath: str) -> dict:
    """
    Full reviewer pipeline for one file: run linter, then summarize with LLM.
    """
    findings = run_pylint(filepath)
    summary = summarize_findings(filepath, findings)
    return {
        "filepath": filepath,
        "raw_findings": findings,
        "summary": summary
    }


if __name__ == "__main__":
    import os
    test_file = "test_dummy.py"
    with open(test_file, "w") as f:
        f.write(
            "import os\n"
            "import sys\n"
            "\n"
            "def add(a,b):\n"
            "    x = 5\n"
            "    return a+b\n"
        )

    result = review_file(test_file)
    print("=== Raw findings count ===")
    print(len(result["raw_findings"]))
    print("\n=== LLM Summary ===")
    print(result["summary"])

    os.remove(test_file)