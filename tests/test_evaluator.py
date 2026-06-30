import json
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evaluator import (
    DEFAULT_MODEL,
    WEIGHTS,
    llm_evaluate_case,
    load_cases,
    mock_evaluate_case,
    select_cases,
    weighted_score,
)


class EvaluatorTest(unittest.TestCase):
    def test_weights_match_business_priority(self):
        self.assertEqual(
            WEIGHTS,
            {
                "helpfulness": 0.40,
                "accuracy": 0.30,
                "truthfulness": 0.20,
                "tone": 0.10,
            },
        )
        self.assertEqual(round(sum(WEIGHTS.values()), 2), 1.00)

    def test_default_qwen_model_is_user_selected_model(self):
        self.assertEqual(DEFAULT_MODEL, "qwen3.6-plus")

    def test_weighted_score_keeps_one_decimal_place(self):
        scores = {
            "helpfulness": 2,
            "accuracy": 4,
            "truthfulness": 5,
            "tone": 4,
        }
        self.assertEqual(weighted_score(scores), 3.4)

    def test_load_cases_joins_auto_replies_and_human_reference(self):
        cases = load_cases(ROOT / "data")
        self.assertEqual(len(cases), 20)
        first = cases[0]
        self.assertEqual(first["id"], "case_01")
        self.assertIn("user_question", first)
        self.assertIn("auto_reply", first)
        self.assertIn("human_reference", first)
        self.assertIn("annotator_notes", first)

    def test_mock_evaluator_flags_correct_but_not_useful_case(self):
        cases = load_cases(ROOT / "data")
        case_08 = next(item for item in cases if item["id"] == "case_08")
        result = mock_evaluate_case(case_08)
        self.assertGreaterEqual(result["scores"]["accuracy"], 4)
        self.assertGreaterEqual(result["scores"]["truthfulness"], 4)
        self.assertLessEqual(result["scores"]["helpfulness"], 3)
        self.assertLess(result["overall"], 4)

    def test_llm_timeout_falls_back_to_mock_result(self):
        cases = load_cases(ROOT / "data")
        with patch("evaluator.call_qwen", side_effect=TimeoutError("timed out")):
            result = llm_evaluate_case(cases[0], retries=0, timeout=1)
        self.assertEqual(result["mode"], "mock_fallback")
        self.assertIn("llm_error", result)

    def test_select_cases_can_limit_api_smoke_test_to_one_case(self):
        cases = load_cases(ROOT / "data")
        selected = select_cases(cases, limit=1)
        self.assertEqual([item["id"] for item in selected], ["case_01"])

    def test_select_cases_can_resume_from_case_id(self):
        cases = load_cases(ROOT / "data")
        selected = select_cases(cases, start="case_08", limit=2)
        self.assertEqual([item["id"] for item in selected], ["case_08", "case_09"])


if __name__ == "__main__":
    unittest.main()
