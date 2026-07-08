import subprocess
import json


def run_pylint(filepath: str):
    """
    Runs pylint on a single Python file and returns a list of findings.
    Each finding has: line, column, type, message, symbol
    """
    try:
        result = subprocess.run(
            ["pylint", filepath, "--output-format=json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        # pylint returns non-zero exit codes even on successful runs with findings,
        # so we don't check returncode here — we just try to parse stdout.
        if not result.stdout.strip():
            return []
        findings = json.loads(result.stdout)
        return findings
    except json.JSONDecodeError:
        # pylint sometimes prints non-JSON warnings to stdout on odd setups
        return [{"error": "Could not parse pylint output", "raw": result.stdout}]
    except subprocess.TimeoutExpired:
        return [{"error": "Linter timed out"}]
    except FileNotFoundError:
        return [{"error": "pylint not installed or not found in PATH"}]


if __name__ == "__main__":
    # Quick manual test against a dummy file with deliberate issues
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

    findings = run_pylint(test_file)
    print(f"Found {len(findings)} issues:")
    for f in findings:
        print(f" - Line {f.get('line')}: {f.get('message')} ({f.get('symbol')})")

    os.remove(test_file)
