import os
import unittest
from datetime import datetime
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.config.loader import load_env_file

load_env_file()

raw_url = os.environ.get("DATABASE_URL")
if not raw_url:
    raise RuntimeError("DATABASE_URL is missing.")

main_url = make_url(raw_url)
if main_url.database != "lead_automation":
    raise RuntimeError(
        "Unexpected DATABASE_URL target; refusing to run repository tests."
    )

TEST_URL = main_url.set(database="lead_automation_test")
TEST_ENGINE = create_engine(TEST_URL, pool_pre_ping=True)

inspector = inspect(TEST_ENGINE)
required_tables = {"alembic_version", "leads", "lead_activities", "lead_score_history"}
missing_tables = required_tables - set(inspector.get_table_names())

if missing_tables:
    TEST_ENGINE.dispose()
    raise RuntimeError(
        f"Test database is missing tables: {sorted(missing_tables)}"
    )

columns = {column["name"] for column in inspector.get_columns("leads")}
if "received_at" not in columns:
    TEST_ENGINE.dispose()
    raise RuntimeError("Test database schema is outdated.")

TestSessionLocal = sessionmaker(
    bind=TEST_ENGINE,
    autoflush=False,
    expire_on_commit=False,
)

from app.db import repository


class TestPostgresRepository(unittest.TestCase):
    def setUp(self):
        with TEST_ENGINE.begin() as connection:
            connection.execute(
                text(
                    "TRUNCATE TABLE lead_score_history, lead_activities, leads "
                    "RESTART IDENTITY CASCADE"
                )
            )

        self.session_patch = patch(
            "app.db.repository.SessionLocal",
            TestSessionLocal,
        )
        self.session_patch.start()

        self.lead = {
            "name": "Test User",
            "job": "AI Automation",
            "city": "Tehran",
            "phone": "09121112233",
            "email": "Test@example.com",
        }

    def tearDown(self):
        self.session_patch.stop()

    def test_email_duplicate_is_case_insensitive(self):
        first = repository.save_lead(self.lead)
        second = repository.save_lead({
            **self.lead,
            "phone": "09123334455",
            "email": "TEST@EXAMPLE.COM",
        })

        self.assertTrue(first["success"])
        self.assertFalse(second["success"])
        self.assertEqual(second["error_type"], "duplicate_email")
        self.assertEqual(len(repository.load_leads()), 1)

    def test_received_at_is_saved_and_loaded(self):
        timestamp = "2026-10-09T10:00:00+00:00"
        result = repository.save_lead({
            **self.lead,
            "received_at": timestamp,
        })

        self.assertTrue(result["success"])
        saved = repository.load_leads()

        self.assertEqual(len(saved), 1)
        self.assertEqual(
            datetime.fromisoformat(saved[0]["received_at"]),
            datetime.fromisoformat(timestamp),
        )

    def test_invalid_received_at_is_rejected(self):
        result = repository.save_lead({
            **self.lead,
            "received_at": "not-a-timestamp",
        })

        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "validation")
        self.assertEqual(repository.load_leads(), [])

    def test_scoring_metadata_is_mapped_correctly(self):
        result = repository.save_lead({
            **self.lead,
            "components": {"fit_score": 80.0},
            "reasons": ["Test reason"],
            "warnings": ["Test warning"],
        })

        self.assertTrue(result["success"])
        saved = repository.load_leads()[0]

        self.assertEqual(
            saved["components"],
            {"fit_score": 80.0},
        )
        self.assertEqual(saved["reasons"], ["Test reason"])
        self.assertEqual(saved["warnings"], ["Test warning"])


if __name__ == "__main__":
    unittest.main()
