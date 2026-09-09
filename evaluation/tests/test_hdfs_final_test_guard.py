from __future__ import annotations

import unittest

from evaluation.runners.run_hdfs_final_test import RELEASE_TOKEN, validate_release


class HdfsFinalTestGuardTests(unittest.TestCase):
    def test_rejects_missing_flag_or_token(self) -> None:
        with self.assertRaises(PermissionError):
            validate_release(release_flag=False, approval_token=RELEASE_TOKEN)
        with self.assertRaises(PermissionError):
            validate_release(release_flag=True, approval_token="wrong")

    def test_allows_explicit_release(self) -> None:
        validate_release(release_flag=True, approval_token=RELEASE_TOKEN)


if __name__ == "__main__":
    unittest.main()
