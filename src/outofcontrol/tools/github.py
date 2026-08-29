from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any

import httpx

from outofcontrol.tools.base import ConfirmCallback, ToolRegistry, ToolResult, ToolSpec
from outofcontrol.tools.pending import PendingConfirmations


def _gh_available() -> bool:
    return shutil.which("gh") is not None


def _run_gh(args: list[str], timeout: int = 60) -> ToolResult:
    try:
        proc = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return ToolResult(ok=False, output="gh CLI not found. Install GitHub CLI or set GITHUB_TOKEN.")
    except subprocess.TimeoutExpired:
        return ToolResult(ok=False, output=f"gh timed out after {timeout}s")
    out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    out = out.strip() or "(no output)"
    if len(out) > 40_000:
        out = out[:40_000] + "\n...[truncated]"
    return ToolResult(ok=proc.returncode == 0, output=out, meta={"exit_code": proc.returncode})


def _api(
    method: str,
    path: str,
    *,
    token: str,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> ToolResult:
    url = path if path.startswith("http") else f"https://api.github.com{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "outofcontrol-agent",
    }
    try:
        with httpx.Client(timeout=45.0) as client:
            r = client.request(method, url, headers=headers, json=json_body, params=params)
            text = r.text
            if len(text) > 40_000:
                text = text[:40_000] + "\n...[truncated]"
            if r.status_code >= 400:
                return ToolResult(ok=False, output=f"GitHub API {r.status_code}: {text}")
            return ToolResult(ok=True, output=text)
    except Exception as e:  # noqa: BLE001
        return ToolResult(ok=False, output=f"GitHub API error: {e}")


def register_github_tools(
    registry: ToolRegistry,
    *,
    default_repo: str | None = None,
    confirm_sensitive: bool = True,
    confirm: ConfirmCallback | None = None,
    pending: PendingConfirmations | None = None,
) -> None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    def _repo(repo: str | None) -> str | None:
        return repo or default_repo

    def github_status() -> ToolResult:
        if _gh_available():
            return _run_gh(["auth", "status"])
        if token:
            return _api("GET", "/user", token=token)
        return ToolResult(
            ok=False,
            output="GitHub not configured. Install `gh` and login, or set GITHUB_TOKEN.",
        )

    def github_issue_list(
        repo: str | None = None,
        state: str = "open",
        limit: int = 20,
        search: str | None = None,
    ) -> ToolResult:
        r = _repo(repo)
        if _gh_available():
            args = ["issue", "list", "--state", state, "--limit", str(limit), "--json", "number,title,author,labels,url,createdAt"]
            if r:
                args += ["--repo", r]
            if search:
                args += ["--search", search]
            return _run_gh(args)
        if not token or not r:
            return ToolResult(ok=False, output="Need gh CLI or GITHUB_TOKEN + repo (owner/name)")
        owner, name = r.split("/", 1)
        params: dict[str, Any] = {"state": state, "per_page": min(limit, 50)}
        return _api("GET", f"/repos/{owner}/{name}/issues", token=token, params=params)

    def github_issue_view(number: int, repo: str | None = None) -> ToolResult:
        r = _repo(repo)
        if _gh_available():
            args = ["issue", "view", str(number), "--json", "number,title,body,author,labels,state,url,comments"]
            if r:
                args += ["--repo", r]
            return _run_gh(args)
        if not token or not r:
            return ToolResult(ok=False, output="Need gh CLI or GITHUB_TOKEN + repo")
        owner, name = r.split("/", 1)
        return _api("GET", f"/repos/{owner}/{name}/issues/{number}", token=token)

    def github_issue_create(
        title: str,
        body: str = "",
        repo: str | None = None,
        labels: str = "",
    ) -> ToolResult:
        r = _repo(repo)
        if _gh_available():
            args = ["issue", "create", "--title", title, "--body", body or ""]
            if r:
                args += ["--repo", r]
            if labels.strip():
                for lab in labels.split(","):
                    lab = lab.strip()
                    if lab:
                        args += ["--label", lab]
            return _run_gh(args)
        if not token or not r:
            return ToolResult(ok=False, output="Need gh CLI or GITHUB_TOKEN + repo")
        owner, name = r.split("/", 1)
        payload: dict[str, Any] = {"title": title, "body": body}
        labs = [x.strip() for x in labels.split(",") if x.strip()]
        if labs:
            payload["labels"] = labs
        return _api("POST", f"/repos/{owner}/{name}/issues", token=token, json_body=payload)

    def github_pr_list(repo: str | None = None, state: str = "open", limit: int = 20) -> ToolResult:
        r = _repo(repo)
        if _gh_available():
            args = [
                "pr",
                "list",
                "--state",
                state,
                "--limit",
                str(limit),
                "--json",
                "number,title,author,url,createdAt,headRefName,isDraft",
            ]
            if r:
                args += ["--repo", r]
            return _run_gh(args)
        if not token or not r:
            return ToolResult(ok=False, output="Need gh CLI or GITHUB_TOKEN + repo")
        owner, name = r.split("/", 1)
        return _api(
            "GET",
            f"/repos/{owner}/{name}/pulls",
            token=token,
            params={"state": state, "per_page": min(limit, 50)},
        )

    def github_pr_view(number: int, repo: str | None = None) -> ToolResult:
        r = _repo(repo)
        if _gh_available():
            args = [
                "pr",
                "view",
                str(number),
                "--json",
                "number,title,body,author,state,url,commits,files,statusCheckRollup,isDraft",
            ]
            if r:
                args += ["--repo", r]
            return _run_gh(args)
        if not token or not r:
            return ToolResult(ok=False, output="Need gh CLI or GITHUB_TOKEN + repo")
        owner, name = r.split("/", 1)
        return _api("GET", f"/repos/{owner}/{name}/pulls/{number}", token=token)

    def github_pr_create(
        title: str,
        body: str = "",
        base: str = "main",
        head: str | None = None,
        draft: bool = True,
        repo: str | None = None,
    ) -> ToolResult:
        r = _repo(repo)
        if _gh_available():
            args = ["pr", "create", "--title", title, "--body", body or "", "--base", base]
            if draft:
                args.append("--draft")
            if head:
                args += ["--head", head]
            if r:
                args += ["--repo", r]
            return _run_gh(args)
        return ToolResult(
            ok=False,
            output="github_pr_create via API needs more repo context; use gh CLI for PR creation.",
        )

    def github_ci_list(repo: str | None = None, limit: int = 10) -> ToolResult:
        r = _repo(repo)
        if _gh_available():
            args = [
                "run",
                "list",
                "--limit",
                str(limit),
                "--json",
                "databaseId,name,status,conclusion,event,headBranch,url,createdAt",
            ]
            if r:
                args += ["--repo", r]
            return _run_gh(args)
        if not token or not r:
            return ToolResult(ok=False, output="Need gh CLI or GITHUB_TOKEN + repo")
        owner, name = r.split("/", 1)
        return _api(
            "GET",
            f"/repos/{owner}/{name}/actions/runs",
            token=token,
            params={"per_page": min(limit, 30)},
        )

    def github_ci_view(run_id: str, repo: str | None = None) -> ToolResult:
        r = _repo(repo)
        if _gh_available():
            args = ["run", "view", str(run_id)]
            if r:
                args += ["--repo", r]
            return _run_gh(args)
        if not token or not r:
            return ToolResult(ok=False, output="Need gh CLI or GITHUB_TOKEN + repo")
        owner, name = r.split("/", 1)
        return _api("GET", f"/repos/{owner}/{name}/actions/runs/{run_id}", token=token)

    def github_ci_watch(run_id: str, repo: str | None = None, timeout_seconds: int = 300) -> ToolResult:
        r = _repo(repo)
        if not _gh_available():
            return ToolResult(ok=False, output="github_ci_watch requires the gh CLI")
        args = ["run", "watch", str(run_id), "--exit-status"]
        if r:
            args += ["--repo", r]
        return _run_gh(args, timeout=timeout_seconds)

    def github_pr_merge(
        number: int,
        repo: str | None = None,
        method: str = "squash",
    ) -> ToolResult:
        r = _repo(repo)
        payload = {"number": number, "repo": r, "method": method}
        if confirm_sensitive:
            if confirm is not None:
                if not confirm("github_pr_merge", payload):
                    return ToolResult(ok=False, output="User denied PR merge")
            elif pending is not None:
                token_id = pending.store("github_pr_merge", payload)
                return ToolResult(
                    ok=False,
                    output="Merging a PR requires confirmation. Call confirm_action with the token.",
                    needs_confirmation=True,
                    confirmation_token=token_id,
                    meta={"kind": "github_pr_merge", **payload},
                )
        if _gh_available():
            args = ["pr", "merge", str(number), f"--{method}"]
            if r:
                args += ["--repo", r]
            return _run_gh(args)
        return ToolResult(ok=False, output="github_pr_merge requires gh CLI")

    for name, desc, params, handler, sensitive in [
        (
            "github_status",
            "Check GitHub auth status (gh or GITHUB_TOKEN).",
            {"type": "object", "properties": {}},
            github_status,
            False,
        ),
        (
            "github_issue_list",
            "List GitHub issues.",
            {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "owner/name"},
                    "state": {"type": "string", "default": "open"},
                    "limit": {"type": "integer", "default": 20},
                    "search": {"type": "string"},
                },
            },
            github_issue_list,
            False,
        ),
        (
            "github_issue_view",
            "View a GitHub issue by number.",
            {
                "type": "object",
                "properties": {
                    "number": {"type": "integer"},
                    "repo": {"type": "string"},
                },
                "required": ["number"],
            },
            github_issue_view,
            False,
        ),
        (
            "github_issue_create",
            "Create a GitHub issue.",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "repo": {"type": "string"},
                    "labels": {"type": "string", "description": "Comma-separated labels"},
                },
                "required": ["title"],
            },
            github_issue_create,
            False,
        ),
        (
            "github_pr_list",
            "List pull requests.",
            {
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "state": {"type": "string", "default": "open"},
                    "limit": {"type": "integer", "default": 20},
                },
            },
            github_pr_list,
            False,
        ),
        (
            "github_pr_view",
            "View a pull request by number (includes checks when using gh).",
            {
                "type": "object",
                "properties": {
                    "number": {"type": "integer"},
                    "repo": {"type": "string"},
                },
                "required": ["number"],
            },
            github_pr_view,
            False,
        ),
        (
            "github_pr_create",
            "Create a pull request (draft by default). Requires gh CLI.",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "base": {"type": "string", "default": "main"},
                    "head": {"type": "string"},
                    "draft": {"type": "boolean", "default": True},
                    "repo": {"type": "string"},
                },
                "required": ["title"],
            },
            github_pr_create,
            False,
        ),
        (
            "github_ci_list",
            "List recent GitHub Actions workflow runs.",
            {
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
            },
            github_ci_list,
            False,
        ),
        (
            "github_ci_view",
            "View a GitHub Actions run by id.",
            {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "repo": {"type": "string"},
                },
                "required": ["run_id"],
            },
            github_ci_view,
            False,
        ),
        (
            "github_ci_watch",
            "Watch a GitHub Actions run until completion (blocking; requires gh).",
            {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "repo": {"type": "string"},
                    "timeout_seconds": {"type": "integer", "default": 300},
                },
                "required": ["run_id"],
            },
            github_ci_watch,
            False,
        ),
        (
            "github_pr_merge",
            "Merge a pull request (requires confirmation). Prefer squash/merge/rebase method.",
            {
                "type": "object",
                "properties": {
                    "number": {"type": "integer"},
                    "repo": {"type": "string"},
                    "method": {"type": "string", "default": "squash", "description": "squash|merge|rebase"},
                },
                "required": ["number"],
            },
            github_pr_merge,
            True,
        ),
    ]:
        registry.register(
            ToolSpec(name=name, description=desc, parameters=params, handler=handler, sensitive=sensitive)
        )
