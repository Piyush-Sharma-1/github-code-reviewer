import os
import shutil
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
from fastapi.responses import RedirectResponse
import httpx
from config import GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET
from fastapi.responses import FileResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from tools.test_runner import install_dependencies
from tools.github_fetcher import try_get_file_content



from tools.github_fetcher import (
    fetch_pr_data,
    get_file_content,
    get_repo_tree,
    is_test_file,
    post_pr_comment,
)
from pipeline import run_pipeline

app = FastAPI()
BASE_URL = "https://github-code-reviewer-6adl.onrender.com"
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Allow the frontend (running on a different port/origin) to call this API
ALLOWED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "https://github-code-reviewer-6adl.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

class ReviewRequest(BaseModel):
    pr_url: str
class PostCommentRequest(BaseModel):
    owner: str
    repo: str
    pr_number: int
    comment_body: str
    user_token: str


@app.post("/post-comment")
def post_comment(req: PostCommentRequest):
    """
    Posts a comment on a PR using the logged-in user's own GitHub token,
    never the server's own GITHUB_TOKEN from .env.
    """
    import requests

    url = f"https://api.github.com/repos/{req.owner}/{req.repo}/issues/{req.pr_number}/comments"
    headers = {
        "Authorization": f"token {req.user_token}",
        "Accept": "application/vnd.github+json",
    }
    response = requests.post(url, headers=headers, json={"body": req.comment_body})

    if response.status_code >= 400:
        return {"success": False, "error": response.json()}

    return {"success": True, "html_url": response.json()["html_url"]}

def is_python_file(filename: str) -> bool:
    return filename.endswith(".py")


def write_file(local_root: str, repo_path: str, content: str) -> str:
    if ".." in repo_path.split("/") or repo_path.startswith("/"):
        raise ValueError(f"Unsafe file path rejected: {repo_path}")

    local_path = os.path.join(local_root, repo_path)
    local_root_abs = os.path.abspath(local_root)
    local_path_abs = os.path.abspath(local_path)

    if not local_path_abs.startswith(local_root_abs):
        raise ValueError(f"Path escapes workdir: {repo_path}")

    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(content)
    return local_path

@app.get("/")
def serve_frontend():
    return FileResponse("frontend.html")

@app.post("/review")
@limiter.limit("5/10minutes")
def review_pr(request: Request, req: ReviewRequest):
    pr_data = fetch_pr_data(req.pr_url)

    changed_py_files = [
        f["filename"] for f in pr_data["changed_files"] if is_python_file(f["filename"])
    ]
    target_files = [f for f in changed_py_files if not is_test_file(f)]

    if not target_files:
        return {"error": "No reviewable Python files changed in this PR."}

    if len(target_files) > 5:
        return {"error": f"This PR changes {len(target_files)} Python files — too many for this tool to review at once (limit: 5)."}
    
    all_paths = get_repo_tree(pr_data["owner"], pr_data["repo"], pr_data["head_branch"])
    test_paths = [p for p in all_paths if p.endswith(".py") and is_test_file(p)]

    workdir = f"pr_workdir_{pr_data['owner']}_{pr_data['repo']}_{pr_data['pr_number']}"
    if os.path.exists(workdir):
        shutil.rmtree(workdir)
    os.makedirs(workdir, exist_ok=True)

    local_target_paths = []
    for repo_path in target_files:
        content = get_file_content(pr_data["owner"], pr_data["repo"], repo_path, pr_data["head_branch"])
        local_target_paths.append(write_file(workdir, repo_path, content))

    for repo_path in test_paths:
        content = get_file_content(pr_data["owner"], pr_data["repo"], repo_path, pr_data["head_branch"])
        write_file(workdir, repo_path, content)

    # Check for and install dependencies, if the repo declares any
    req_content = try_get_file_content(pr_data["owner"], pr_data["repo"], "requirements.txt", pr_data["head_branch"])
    deps_dir = None
    if req_content:
        write_file(workdir, "requirements.txt", req_content)
        install_result = install_dependencies(workdir)
        if install_result.get("installed"):
            deps_dir = install_result.get("deps_dir")

    results = []
    for target_file in local_target_paths:
        result = run_pipeline(target_file, workdir, deps_dir=deps_dir)
        results.append({
            "file": target_file,
            "final_status": result["final_status"],
            "iterations": result["iteration_count"],
            "tests_passed": result["test_result"].get("passed"),
            "report": result["final_report"],
        })

    shutil.rmtree(workdir)

    return {
        "pr_title": pr_data["title"],
        "owner": pr_data["owner"],
        "repo": pr_data["repo"],
        "pr_number": pr_data["pr_number"],
        "results": results,
    }

@app.get("/auth/login")
def github_login():
    """
    Redirects the user to GitHub's OAuth consent screen.
    'repo' scope is needed later (Step 7) to let them post PR comments.
    """
    github_auth_url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&scope=repo"
        f"&redirect_uri={BASE_URL}/auth/callback"
    )
    return RedirectResponse(github_auth_url)


@app.get("/auth/callback")
async def github_callback(code: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
            },
        )
        token_data = response.json()

    print("GitHub token exchange:", "success" if token_data.get("access_token") else f"failed — {token_data.get('error', 'unknown error')}")
    access_token = token_data.get("access_token")
    if not access_token:
        return RedirectResponse(f"{BASE_URL}/auth/failed")

    frontend_url = f"{BASE_URL}/#token={access_token}"
    return RedirectResponse(frontend_url)


@app.get("/auth/failed")
def auth_failed():
    return {"error": "GitHub authorization failed. Check the backend terminal for details."}


@app.websocket("/ws/review")
async def review_pr_ws(websocket: WebSocket):
    await websocket.accept()
    # Manual rate limit check for WebSocket (slowapi's decorator targets HTTP routes only)
    client_ip = websocket.client.host
    if not hasattr(app.state, "ws_calls"):
        app.state.ws_calls = {}
    import time
    now = time.time()
    calls = [t for t in app.state.ws_calls.get(client_ip, []) if now - t < 600]  # last 10 minutes
    if len(calls) >= 5:
        await websocket.send_json({"event": "error", "data": {"message": "Rate limit exceeded. Try again later."}})
        await websocket.close()
        return
    calls.append(now)
    app.state.ws_calls[client_ip] = calls

    try:
    
        data = await websocket.receive_json()
        pr_url = data["pr_url"]

        loop = asyncio.get_event_loop()

        # Since run_pipeline is synchronous, we run it in a background thread
        # and use call_soon_threadsafe to safely push events back onto the
        # asyncio event loop from that other thread.
        def send_event(event: str, payload: dict):
            asyncio.run_coroutine_threadsafe(
                websocket.send_json({"event": event, "data": payload}),
                loop
            )

        await websocket.send_json({"event": "fetching_pr", "data": {"pr_url": pr_url}})

        pr_data = fetch_pr_data(pr_url)
        await websocket.send_json({
            "event": "pr_fetched",
            "data": {"title": pr_data["title"], "head_branch": pr_data["head_branch"]}
        })

        changed_py_files = [
            f["filename"] for f in pr_data["changed_files"] if is_python_file(f["filename"])
        ]
        target_files = [f for f in changed_py_files if not is_test_file(f)]

        if not target_files:
            await websocket.send_json({"event": "error", "data": {"message": "No reviewable Python files changed."}})
            await websocket.close()
            return

        if len(target_files) > 5:
            await websocket.send_json({"event": "error", "data": {"message": f"This PR changes {len(target_files)} files — too many to review at once (limit: 5)."}})
            await websocket.close()
            return
        
        all_paths = get_repo_tree(pr_data["owner"], pr_data["repo"], pr_data["head_branch"])
        test_paths = [p for p in all_paths if p.endswith(".py") and is_test_file(p)]

        workdir = f"pr_workdir_{pr_data['owner']}_{pr_data['repo']}_{pr_data['pr_number']}"
        if os.path.exists(workdir):
            shutil.rmtree(workdir)
        os.makedirs(workdir, exist_ok=True)

        local_target_paths = []
        for repo_path in target_files:
            content = get_file_content(pr_data["owner"], pr_data["repo"], repo_path, pr_data["head_branch"])
            local_target_paths.append(write_file(workdir, repo_path, content))

        for repo_path in test_paths:
            content = get_file_content(pr_data["owner"], pr_data["repo"], repo_path, pr_data["head_branch"])
            write_file(workdir, repo_path, content)

        req_content = try_get_file_content(pr_data["owner"], pr_data["repo"], "requirements.txt", pr_data["head_branch"])
        deps_dir = None
        if req_content:
            write_file(workdir, "requirements.txt", req_content)
            await websocket.send_json({"event": "installing_deps", "data": {}})
            install_result = install_dependencies(workdir)
            if install_result.get("installed"):
                deps_dir = install_result.get("deps_dir")
                await websocket.send_json({"event": "deps_installed", "data": {"success": True}})
            else:
                await websocket.send_json({"event": "deps_installed", "data": {"success": False, "output": install_result.get("output", "")}})

        await websocket.send_json({"event": "files_ready", "data": {"targets": local_target_paths}})

        for target_file in local_target_paths:
            await websocket.send_json({"event": "pipeline_start", "data": {"file": target_file}})

            result = await loop.run_in_executor(
                None, lambda: run_pipeline(target_file, workdir, progress_callback=send_event, deps_dir=deps_dir)
            )

            await websocket.send_json({
                "event": "pipeline_done",
                "data": {
                    "file": target_file,
                    "final_status": result["final_status"],
                    "iterations": result["iteration_count"],
                    "tests_passed": result["test_result"].get("passed"),
                    "report": result["final_report"],
                }
            })

        shutil.rmtree(workdir)
        await websocket.send_json({"event": "all_done", "data": {}})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"event": "error", "data": {"message": str(e)}})
    finally:
        await websocket.close()
