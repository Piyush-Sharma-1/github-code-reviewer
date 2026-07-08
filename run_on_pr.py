import os
from tools.github_fetcher import (
    fetch_pr_data,
    get_file_content,
    get_repo_tree,
    is_test_file,
    post_pr_comment,
)
from pipeline import run_pipeline

PR_URL = "https://github.com/Piyush-Sharma-1/test-repo-ai-agent/pull/1"

WORKDIR = "pr_workdir"


def is_python_file(filename: str) -> bool:
    return filename.endswith(".py")


def write_file(local_root: str, repo_path: str, content: str) -> str:
    local_path = os.path.join(local_root, repo_path)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(content)
    return local_path


def main():
    print(f"Fetching PR data for: {PR_URL}")
    pr_data = fetch_pr_data(PR_URL)

    print("PR Title:", pr_data["title"])
    print("Head branch:", pr_data["head_branch"])
    print("Changed files:")
    for f in pr_data["changed_files"]:
        print(f"  - {f['filename']} (+{f['additions']}/-{f['deletions']})")

    changed_py_files = [
        f["filename"] for f in pr_data["changed_files"] if is_python_file(f["filename"])
    ]
    if not changed_py_files:
        print("No Python files changed in this PR. Nothing to review.")
        return

    # Split changed files into "targets to fix" vs "test files" (we don't fix test files themselves)
    target_files = [f for f in changed_py_files if not is_test_file(f)]
    if not target_files:
        print("Only test files were changed — nothing to review/fix.")
        return

    print("\nDiscovering full repo tree to find test files...")
    all_paths = get_repo_tree(pr_data["owner"], pr_data["repo"], pr_data["head_branch"])
    test_paths = [p for p in all_paths if p.endswith(".py") and is_test_file(p)]
    print(f"Found {len(test_paths)} test file(s) in the repo:")
    for t in test_paths:
        print(f"  - {t}")

    if os.path.exists(WORKDIR):
        import shutil
        shutil.rmtree(WORKDIR)
    os.makedirs(WORKDIR, exist_ok=True)

    # Fetch and write all changed target files (preserving folder structure)
    local_target_paths = []
    for repo_path in target_files:
        content = get_file_content(pr_data["owner"], pr_data["repo"], repo_path, pr_data["head_branch"])
        local_path = write_file(WORKDIR, repo_path, content)
        local_target_paths.append(local_path)
        print(f"Wrote target: {repo_path} -> {local_path}")

    # Fetch and write all discovered test files (preserving folder structure)
    for repo_path in test_paths:
        content = get_file_content(pr_data["owner"], pr_data["repo"], repo_path, pr_data["head_branch"])
        local_path = write_file(WORKDIR, repo_path, content)
        print(f"Wrote test file: {repo_path} -> {local_path}")

    # Run the pipeline once per changed target file, using the whole workdir as the test scope
    for target_file in local_target_paths:
        print(f"\n{'='*60}\nRunning pipeline against: {target_file}\n{'='*60}")
        result = run_pipeline(target_file, WORKDIR)

        print("\n---------- FINAL REPORT ----------")
        print(result["final_report"])

        print("\nPosting comment to PR...")
        posted = post_pr_comment(
            pr_data["owner"], pr_data["repo"], pr_data["pr_number"], result["final_report"]
        )
        print("Comment posted:", posted["html_url"])


if __name__ == "__main__":
    main()