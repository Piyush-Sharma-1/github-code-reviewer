import re
import requests
from config import GITHUB_TOKEN

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}


def parse_pr_url(pr_url: str):
    """
    Extracts owner, repo, and PR number from a GitHub PR URL like:
    https://github.com/owner/repo/pull/123
    """
    pattern = r"github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    match = re.search(pattern, pr_url)
    if not match:
        raise ValueError(f"Could not parse PR URL: {pr_url}")
    owner, repo, pr_number = match.groups()
    return owner, repo, int(pr_number)


def get_pr_files(owner: str, repo: str, pr_number: int):
    """
    Returns a list of changed files in the PR, each with:
    filename, status, additions, deletions, patch (the diff text)
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def get_pr_details(owner: str, repo: str, pr_number: int):
    """
    Returns metadata about the PR itself (title, description, branch names, etc.)
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()

def get_file_content(owner: str, repo: str, filepath: str, ref: str) -> str:
    """
    Fetches the raw content of a single file at a specific branch/ref
    using the GitHub Contents API.
    """
    import base64

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{filepath}"
    response = requests.get(url, headers=HEADERS, params={"ref": ref})
    response.raise_for_status()
    data = response.json()

    if data.get("encoding") != "base64":
        raise ValueError(f"Unexpected encoding for {filepath}: {data.get('encoding')}")

    return base64.b64decode(data["content"]).decode("utf-8")

def try_get_file_content(owner: str, repo: str, filepath: str, ref: str):
    """
    Like get_file_content, but returns None instead of raising if the file
    doesn't exist (e.g. checking for an optional requirements.txt).
    """
    try:
        return get_file_content(owner, repo, filepath, ref)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        raise

def get_repo_tree(owner: str, repo: str, ref: str):
    """
    Returns the full recursive list of file paths in the repo at a given
    branch/commit ref, using the Git Trees API.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{ref}"
    response = requests.get(url, headers=HEADERS, params={"recursive": "1"})
    response.raise_for_status()
    data = response.json()
    return [item["path"] for item in data.get("tree", []) if item["type"] == "blob"]


def is_test_file(path: str) -> bool:
    """
    Heuristic test-file detection: matches common pytest conventions.
    """
    filename = path.split("/")[-1]
    return (
        filename.startswith("test_")
        or filename.endswith("_test.py")
        or "/tests/" in f"/{path}"
    )


def post_pr_comment(owner: str, repo: str, pr_number: int, comment_body: str):
    """
    Posts a comment on a PR (PRs use the Issues API for comments in GitHub's API model).
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    response = requests.post(url, headers=HEADERS, json={"body": comment_body})
    response.raise_for_status()
    return response.json()


def fetch_pr_data(pr_url: str):
    """
    Main entry point: given a PR URL, returns everything downstream
    agents need — changed files, diffs, and PR metadata.
    """
    owner, repo, pr_number = parse_pr_url(pr_url)

    pr_details = get_pr_details(owner, repo, pr_number)
    pr_files = get_pr_files(owner, repo, pr_number)

    changed_files = []
    for f in pr_files:
        changed_files.append({
            "filename": f["filename"],
            "status": f["status"],
            "additions": f["additions"],
            "deletions": f["deletions"],
            "patch": f.get("patch", "")  # some files (binary, renamed) may have no patch
        })

    return {
        "owner": owner,
        "repo": repo,
        "pr_number": pr_number,
        "title": pr_details.get("title", ""),
        "base_branch": pr_details["base"]["ref"],
        "head_branch": pr_details["head"]["ref"],
        "changed_files": changed_files
    }


if __name__ == "__main__":
    # Quick manual test — replace this URL with any real public PR to try it
    test_url = "https://github.com/pallets/flask/pull/5650"
    data = fetch_pr_data(test_url)
    print("PR Title:", data["title"])
    print("Base branch:", data["base_branch"])
    print("Head branch:", data["head_branch"])
    print("Changed files:")
    for f in data["changed_files"]:
        print(f"  - {f['filename']} (+{f['additions']}/-{f['deletions']})")