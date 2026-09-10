"""Shared explicit-release and clean-worktree guards for sealed evaluations."""

from __future__ import annotations


def validate_release(*, release_flag: bool, approval_token: str | None, required_token: str, benchmark: str) -> None:
    if not release_flag or approval_token != required_token:
        raise PermissionError(
            f"{benchmark} scoring requires --release-sealed-test and "
            f"--approval-token {required_token}"
        )


def require_clean_worktree(status: str) -> None:
    if status.strip():
        raise RuntimeError(
            "Refusing sealed scoring from a dirty working tree; commit or stash unrelated changes first"
        )
