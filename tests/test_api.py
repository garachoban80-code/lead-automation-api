import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.config.loader import load_env_file

load_env_file()

raw_url = os.environ.get("DATABASE_URL")
if not raw_url:
    raise RuntimeError("DATABASE_URL is missing; API tests cannot start.")

main_url = make_url(raw_url)
if main_url.database != "lead_automation":
    raise RuntimeError(
        "Expected DATABASE_URL to target lead_automation. "
        "Refusing to initialize API tests."
    )

TEST_URL = main_url.set(database="lead_automation_test")
TEST_ENGINE = create_engine(TEST_URL, pool_pre_ping=True)

inspector = inspect(TEST_ENGINE)
required_tables = {"alembic_version", "leads", "lead_activities"}
missing_tables = required_tables - set(inspector.get_table_names())

if missing_tables:
    TEST_ENGINE.dispose()
    raise RuntimeError(
        f"Test database is missing tables: {sorted(missing_tables)}"
    )

lead_columns = {column["name"] for column in inspector.get_columns("leads")}
if "received_at" not in lead_columns:
    TEST_ENGINE.dispose()
    raise RuntimeError(
        "Test database schema is outdated. Apply migrations first."
    )

TestSessionLocal = sessionmaker(
    bind=TEST_ENGINE,
    autoflush=False,
    expire_on_commit=False,
)

from app.db import repository
from lead_api import app


class TestLeadAPI(unittest.TestCase):
    def setUp(self):
        # Clear only the dedicated test database.
        with TEST_ENGINE.begin() as connection:
            connection.execute(
                text(
                    "TRUNCATE TABLE lead_activities, leads "
                    "RESTART IDENTITY CASCADE"
                )
            )

        self.storage_patch = patch(
            "app.db.repository.SessionLocal",
            TestSessionLocal,
        )
        self.storage_patch.start()

        self.api_key = "test-api-key-" + ("x" * 40)
        self.env_patch = patch.dict(
            os.environ,
            {"API_KEY": self.api_key},
        )
        self.env_patch.start()

        self.client = TestClient(
            app,
            headers={"X-API-Key": self.api_key},
        )

        self.basic_lead = {
            "name": "Test User",
            "job": "AI Automation",
            "city": "Tehran",
            "phone": "09121112233",
            "email": "test@example.com",
        }

    def tearDown(self):
        self.client.close()
        self.env_patch.stop()
        self.storage_patch.stop()

    def test_health_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["message"],
            "Lead API is running",
        )

    def test_valid_lead_is_saved(self):
        response = self.client.post("/webhook", json=self.basic_lead)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertIsInstance(response.json().get("lead_id"), int)
        self.assertGreater(response.json()["lead_id"], 0)

        saved = repository.load_leads()
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["phone"], self.basic_lead["phone"])
        self.assertEqual(saved[0]["email"], self.basic_lead["email"])

    def test_duplicate_phone_returns_conflict(self):
        first = self.client.post("/webhook", json=self.basic_lead)
        second_lead = {
            **self.basic_lead,
            "email": "another@example.com",
        }
        second = self.client.post("/webhook", json=second_lead)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)

    def test_duplicate_email_returns_conflict(self):
        self.client.post("/webhook", json=self.basic_lead)
        second_lead = {
            **self.basic_lead,
            "phone": "09123334455",
        }
        response = self.client.post("/webhook", json=second_lead)

        self.assertEqual(response.status_code, 409)

    def test_invalid_phone_is_rejected(self):
        lead = {**self.basic_lead, "phone": "12345"}
        response = self.client.post("/webhook", json=lead)

        self.assertEqual(response.status_code, 400)

    def test_unknown_fields_are_rejected(self):
        lead = {**self.basic_lead, "unexpected_field": "value"}
        response = self.client.post("/webhook", json=lead)

        self.assertEqual(response.status_code, 422)

    def test_qualified_lead_without_icp_is_unclassified(self):
        lead = {
            **self.basic_lead,
            "budget": "confirmed",
            "timeline": "this_month",
            "need": "clear",
        }

        response = self.client.post("/qualified-lead", json=lead)

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json().get("lead_id"), int)
        self.assertGreater(response.json()["lead_id"], 0)
        result = response.json()["lead"]
        self.assertIsNone(result["score"])
        self.assertEqual(result["category"], "unclassified")
        self.assertEqual(
            result["scoring_status"],
            "scoring_configuration_incomplete",
        )

        saved = repository.load_leads()
        self.assertEqual(len(saved), 1)
        self.assertIn("received_at", saved[0])
        self.assertIn("components", saved[0])
        self.assertIn("reasons", saved[0])
        self.assertIn("warnings", saved[0])

    def test_client_cannot_forge_activity_history(self):
        lead = {
            **self.basic_lead,
            "budget": "confirmed",
            "timeline": "this_month",
            "need": "clear",
            "activities": [
                {
                    "type": "quote_requested",
                    "occurred_at": "2026-10-09T10:00:00+00:00",
                }
            ],
        }

        response = self.client.post("/qualified-lead", json=lead)
        self.assertEqual(response.status_code, 422)

    def test_protected_endpoint_rejects_invalid_api_key(self):
        response = self.client.get(
            "/report",
            headers={"X-API-Key": "wrong-key"},
        )
        self.assertEqual(response.status_code, 401)

    def test_protected_endpoint_fails_closed_without_configuration(self):
        with patch.dict(os.environ, {"API_KEY": ""}):
            response = self.client.get("/report")

        self.assertEqual(response.status_code, 503)

    def test_report_with_empty_storage(self):
        response = self.client.get("/report")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_leads"], 0)


if __name__ == "__main__":
    unittest.main()
