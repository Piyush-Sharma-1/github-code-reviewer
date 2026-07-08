from langchain_groq import ChatGroq
from config import GROQ_API_KEY, LLM_MODEL

llm = ChatGroq(model=LLM_MODEL, api_key=GROQ_API_KEY, temperature=0)


def propose_fix(filepath: str, original_code: str, findings: list) -> str:
    if not findings:
        return original_code  # nothing to fix

    findings_text = "\n".join(
        f"{i+1}. Line {f.get('line', '?')}: {f.get('message', '')} ({f.get('symbol', f.get('error', 'unknown'))})"
        for i, f in enumerate(findings)
    )

    prompt = f"""You are a precise code-fixing assistant.

FILE: {filepath}

ORIGINAL CODE (line numbers shown for reference, do not include them in your output):
{original_code}

LINTER ISSUES TO FIX (there are {len(findings)} issues, you must fix ALL of them):
{findings_text}

STRICT RULES:
1. You MUST fix every single issue listed above. Go through the list one by one before answering.
2. If an issue says "unused import", DELETE that import line entirely.
3. If an issue says "unused variable", DELETE that variable or use it meaningfully - do not just rename it.
4. If an issue says "missing module docstring", add a SHORT one-line docstring as the VERY FIRST line of the file, before any imports.
5. If an issue says "missing function docstring", add a SHORT one-line docstring as the first line inside that function.
6. Fix spacing/formatting issues exactly as flagged (e.g. "a,b" should become "a, b").
7. Do NOT change logic, rename functions/variables (other than removing unused ones), or refactor anything not listed.
8. Do NOT add any new imports, variables, or statements that were not in the original code - only remove or modify what's listed.
9. Ensure the file ends with exactly one newline character and no trailing blank lines.
10. Return ONLY valid, executable Python code - nothing else.
11. Do NOT write sentences explaining what you removed or why. Do NOT narrate your changes inside the file.
12. Every single line of your output must be valid Python syntax (code, a string, or a comment starting with #).
13. IMPORTANT: a docstring (triple-quoted string right after a module/function definition) is NOT the same as a # comment. When asked to add a docstring, you MUST use triple quotes \"\"\"like this\"\"\", never a # comment.
14. Return ONLY the corrected full file content. No markdown fences, no explanation outside the code, no preamble.
Before answering, mentally check: does your output still contain any of the {len(findings)} issues listed, or any new import/variable that wasn't in the original? If yes, fix it now.
"""

    response = llm.invoke(prompt)
    fixed_code = response.content.strip()

    if fixed_code.startswith("```"):
        lines = fixed_code.split("\n")
        lines = lines[1:] if lines[0].startswith("```") else lines
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        fixed_code = "\n".join(lines)

    # Ensure exactly one trailing newline
    fixed_code = fixed_code.rstrip("\n") + "\n"

    # Safety net: verify the LLM's output is actually valid Python syntax
    try:
        compile(fixed_code, filepath, "exec")
    except SyntaxError as e:
        print(f"WARNING: Fixer produced invalid Python syntax: {e}")
        print("Falling back to original code — this fix attempt will be rejected.")
        return original_code

    return fixed_code


if __name__ == "__main__":
    import os
    from tools.linter_runner import run_pylint

    test_file = "test_dummy.py"
    original = (
        "import os\n"
        "import sys\n"
        "\n"
        "def add(a,b):\n"
        "    x = 5\n"
        "    return a+b\n"
    )
    with open(test_file, "w") as f:
        f.write(original)
    print("=== ORIGINAL CODE ===")
    print(original)
   
    findings_before = run_pylint(test_file)
    print(f"=== ISSUES BEFORE FIX: {len(findings_before)} ===")
    for f in findings_before:
        print(f" - {f.get('message')} ({f.get('symbol')})")

    fixed_code = propose_fix(test_file, original, findings_before)

    print("\n=== PROPOSED FIX ===")
    print(fixed_code)

    with open(test_file, "w") as f:
        f.write(fixed_code)
    findings_after = run_pylint(test_file)

    print(f"\n=== ISSUES AFTER FIX: {len(findings_after)} ===")
    for f in findings_after:
        print(f" - {f.get('message')} ({f.get('symbol')})")

    os.remove(test_file)