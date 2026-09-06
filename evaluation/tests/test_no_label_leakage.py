from __future__ import annotations

import unittest

from evaluation.adapters.bgl_adapter import ALLOWED_BGL_INPUT, FORBIDDEN_FEATURE_TOKENS


class LabelLeakageTests(unittest.TestCase):
    def test_bgl_allow_list_has_no_forbidden_columns(self) -> None:
        for column in ALLOWED_BGL_INPUT:
            with self.subTest(column=column):
                self.assertFalse(
                    any(token in column.casefold() for token in FORBIDDEN_FEATURE_TOKENS)
                )


if __name__ == "__main__":
    unittest.main()
