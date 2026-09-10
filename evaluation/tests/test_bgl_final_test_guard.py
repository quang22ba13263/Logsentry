from __future__ import annotations

import unittest

from evaluation.runners.final_guard import require_clean_worktree, validate_release
from evaluation.runners.run_bgl_final_test import RELEASE_TOKEN


class BglFinalTestGuardTests(unittest.TestCase):
    def test_requires_exact_release(self) -> None:
        with self.assertRaises(PermissionError):
            validate_release(
                release_flag=True,
                approval_token="wrong",
                required_token=RELEASE_TOKEN,
                benchmark="BGL post-diagnostic confirmation",
            )
        validate_release(
            release_flag=True,
            approval_token=RELEASE_TOKEN,
            required_token=RELEASE_TOKEN,
            benchmark="BGL post-diagnostic confirmation",
        )

    def test_requires_clean_worktree(self) -> None:
        require_clean_worktree("")
        with self.assertRaises(RuntimeError):
            require_clean_worktree(" M unrelated.py\n")


if __name__ == "__main__":
    unittest.main()
