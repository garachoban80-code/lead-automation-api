import copy
import unittest
from datetime import datetime, timezone

from app.services.scoring_service import (
    load_scoring_config,
    score_lead,
)


class TestScoringService(unittest.TestCase):
    def setUp(self):
        self.config = copy.deepcopy(load_scoring_config())

        self.config["fit"] = {
            "target_industries": ["marketing agency"],
            "adjacent_industries": ["consulting"],
            "target_company_sizes": ["small"],
            "decision_maker_roles": ["owner"],
            "influencer_roles": ["manager"],
            "service_regions": ["iran"],
        }

        self.now = datetime(2026, 10, 1, tzinfo=timezone.utc)

        self.lead = {
            "industry": "marketing agency",
            "company_size": "small",
            "contact_role": "owner",
            "service_region": "iran",
            "budget": "confirmed",
            "timeline": "this_month",
            "activities": [],
        }

    def test_missing_icp_profile_does_not_create_final_score(self):
        config = copy.deepcopy(self.config)
        config["fit"]["target_industries"] = []
        config["fit"]["adjacent_industries"] = []
        config["fit"]["target_company_sizes"] = []
        config["fit"]["decision_maker_roles"] = []
        config["fit"]["influencer_roles"] = []
        config["fit"]["service_regions"] = []

        result = score_lead(self.lead, config=config, now=self.now)

        self.assertIsNone(result["score"])
        self.assertEqual(result["category"], "unclassified")
        self.assertEqual(
            result["scoring_status"],
            "scoring_configuration_incomplete",
        )

    def test_complete_matching_profile_has_full_fit_score(self):
        result = score_lead(
            self.lead,
            config=self.config,
            now=self.now,
        )

        self.assertEqual(result["components"]["fit_score"], 100)
        self.assertEqual(result["scoring_status"], "scored")
        self.assertEqual(result["model_type"], "transparent_heuristic")

    def test_combines_fit_and_intent_with_configured_weights(self):
        result = score_lead(
            self.lead,
            config=self.config,
            now=self.now,
        )

        self.assertEqual(result["components"]["intent_raw"], 40)
        self.assertEqual(result["components"]["intent_score"], 40)
        self.assertEqual(result["score"], 64)
        self.assertEqual(result["category"], "warm")

    def test_recent_activity_contributes_more_than_old_activity(self):
        recent = copy.deepcopy(self.lead)
        recent["activities"] = [{
            "type": "pricing_page_view",
            "occurred_at": "2026-10-01T00:00:00+00:00",
        }]

        old = copy.deepcopy(self.lead)
        old["activities"] = [{
            "type": "pricing_page_view",
            "occurred_at": "2026-08-31T00:00:00+00:00",
        }]

        recent_result = score_lead(
            recent,
            config=self.config,
            now=self.now,
        )
        old_result = score_lead(
            old,
            config=self.config,
            now=self.now,
        )

        self.assertEqual(recent_result["components"]["intent_raw"], 45)
        self.assertEqual(old_result["components"]["intent_raw"], 40)

    def test_outside_service_area_penalty_is_explained(self):
        result = score_lead(
            {**self.lead, "outside_service_area": True},
            config=self.config,
            now=self.now,
        )

        self.assertEqual(result["score"], 29)
        self.assertEqual(
            result["components"]["negative_signals"]["outside_service_area"],
            35,
        )
        self.assertTrue(
            any("outside_service_area" in reason for reason in result["reasons"])
        )

    def test_explicit_disqualification_blocks_final_score(self):
        result = score_lead(
            {**self.lead, "explicit_disqualification": True},
            config=self.config,
            now=self.now,
        )

        self.assertIsNone(result["score"])
        self.assertEqual(result["category"], "disqualified")
        self.assertEqual(result["scoring_status"], "disqualified")

    def test_invalid_activity_timestamp_is_skipped_with_warning(self):
        lead = copy.deepcopy(self.lead)
        lead["activities"] = [{
            "type": "pricing_page_view",
            "occurred_at": "not-a-date",
        }]

        result = score_lead(
            lead,
            config=self.config,
            now=self.now,
        )

        self.assertEqual(result["components"]["intent_raw"], 40)
        self.assertTrue(result["warnings"])

    def test_future_activity_is_not_scored(self):
        lead = copy.deepcopy(self.lead)
        lead["activities"] = [{
            "type": "quote_requested",
            "occurred_at": "2026-10-02T00:00:00+00:00",
        }]

        result = score_lead(
            lead,
            config=self.config,
            now=self.now,
        )

        self.assertEqual(result["components"]["intent_raw"], 40)
        self.assertTrue(result["warnings"])

    def test_result_does_not_claim_purchase_probability(self):
        result = score_lead(
            self.lead,
            config=self.config,
            now=self.now,
        )

        self.assertNotIn("purchase_probability", result)
        self.assertEqual(result["model_type"], "transparent_heuristic")
        self.assertIn("components", result)
        self.assertIn("reasons", result)


if __name__ == "__main__":
    unittest.main()
