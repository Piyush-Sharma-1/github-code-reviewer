import subprocess
import os

try:
    import resource  # POSIX only (Linux/Mac) — not available on Windows
    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False


def _limit_resources():
    """
    Runs inside the child process right before exec (POSIX only).
    Caps CPU time, memory, and process count so a malicious or runaway
    test can't consume unbounded resources or fork-bomb the host.
    On Windows this is skipped — the timeout below is still enforced everywhere.
    """
    if not HAS_RESOURCE:
        return
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))                          # 30 CPU seconds max
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))  # 512MB memory max
    resource.setrlimit(resource.RLIMIT_NPROC, (50, 50))                        # max 50 processes/threads
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))                           # no core dumps


def _minimal_env():
    """
    Builds a stripped-down environment for the test subprocess so untrusted
    test code cannot read our API keys or other secrets via os.environ,
    while keeping just enough for Python/pytest to actually run.
    """
    allowed_keys = [
        "PATH", "SYSTEMROOT", "TEMP", "TMP", "PATHEXT",
        "HOMEDRIVE", "HOMEPATH", "USERPROFILE",
    ]
    return {k: v for k, v in os.environ.items() if k in allowed_keys}


def run_tests(test_path: str, timeout: int = 60) -> dict:
    """
    Runs pytest against a given file or directory, sandboxed:
    - stripped-down environment (no API keys/secrets exposed)
    - resource limits on CPU/memory/processes (POSIX only)
    - hard timeout (all platforms)
    - working directory locked to the test_path itself

    Returns a dict with: passed (bool), output (str), returncode (int)
    """
    try:
        result = subprocess.run(
            ["pytest", ".", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=test_path,
            env=_minimal_env(),
            preexec_fn=_limit_resources if HAS_RESOURCE else None,
        )
        return {
            "passed": result.returncode == 0,
            "output": result.stdout + "\n" + result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "output": "Test run timed out (possible infinite loop or runaway process).",
            "returncode": -1,
        }
    except FileNotFoundError:
        return {
            "passed": False,
            "output": "pytest not installed or not found in PATH.",
            "returncode": -1,
        }


if __name__ == "__main__":
    import os
    os.makedirs("test_sandbox", exist_ok=True)
    with open("test_sandbox/calc.py", "w") as f:
        f.write(
            "def add(a, b):\n"
            "    return a + b\n"
        )
    with open("test_sandbox/test_calc.py", "w") as f:
        f.write(
            "from calc import add\n"
            "\n"
            "def test_add():\n"
            "    assert add(2, 3) == 5\n"
            "\n"
            "def test_add_negative():\n"
            "    assert add(-1, -1) == -2\n"
        )

    result = run_tests("test_sandbox")
    print("=== PASSED ===")
    print(result["passed"])
    print("\n=== OUTPUT ===")
    print(result["output"])

    import shutil
    shutil.rmtree("test_sandbox")