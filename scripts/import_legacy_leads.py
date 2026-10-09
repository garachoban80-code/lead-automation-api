import argparse
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.config.loader import load_env_file
SOURCE = ROOT / "leads.json"
REQUIRED = ("name", "job", "city", "phone", "email")
CATEGORIES = {"hot", "warm", "cold"}
LIMITS = {
    "name": 200,
    "job": 200,
    "city": 120,
    "phone": 20,
    "email": 320,
    "industry": 120,
    "company_size": 80,
    "contact_role": 120,
    "service_region": 120,
    "budget": 100,
    "timeline": 100,
    "category": 30,
    "scoring_status": 50,
    "model_type": 50,
    "config_version": 80,
}


def parse_timestamp(value):
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Invalid received_at")
    result = datetime.fromisoformat(
        value.strip().replace("Z", "+00:00")
    )
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def source_conflicts(records):
    groups = defaultdict(list)

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        email = record.get("email")
        phone = record.get("phone")

        if isinstance(email, str) and email.strip():
            groups[("email", email.strip().casefold())].append(index)
        if isinstance(phone, str) and phone.strip():
            groups[("phone", phone.strip())].append(index)

    conflicts = set()
    for indexes in groups.values():
        if len(indexes) > 1:
            conflicts.update(indexes)
    return conflicts


def prepare_record(record):
    if not isinstance(record, dict):
        raise ValueError("Not a JSON object")

    for field in REQUIRED:
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Missing or invalid required field")

    for field, limit in LIMITS.items():
        value = record.get(field)
        if value is not None and (
            not isinstance(value, str) or len(value) > limit
        ):
            raise ValueError("Invalid field type or length")

    phone = record["phone"].strip()
    email = record["email"].strip()

    if (
        not phone.isdigit()
        or len(phone) != 11
        or not phone.startswith("09")
    ):
        raise ValueError("Invalid phone")

    if (
        email.count("@") != 1
        or any(char.isspace() for char in email)
    ):
        raise ValueError("Invalid email")

    score = record.get("score")
    if score is not None:
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(score)
            or not 0 <= score <= 100
        ):
            raise ValueError("Invalid score")

    category = record.get("category")
    if score is None:
        if category not in (None, "unclassified"):
            raise ValueError("Category conflicts with missing score")
        category = "unclassified"
    elif category not in CATEGORIES:
        raise ValueError("Invalid category for scored record")

    reasons = record.get("score_reasons", record.get("reasons"))
    components = record.get(
        "score_components", record.get("components")
    )
    warnings = record.get("score_warnings", record.get("warnings"))

    if reasons is not None and not isinstance(reasons, list):
        raise ValueError("Invalid reasons")
    if components is not None and not isinstance(components, dict):
        raise ValueError("Invalid score components")
    if warnings is not None and not isinstance(warnings, list):
        raise ValueError("Invalid warnings")

    received_at = parse_timestamp(record.get("received_at"))

    values = {
        field: record.get(field)
        for field in (
            "industry",
            "company_size",
            "contact_role",
            "service_region",
            "budget",
            "timeline",
            "need",
        )
    }
    values.update({
        "name": record["name"],
        "job": record["job"],
        "city": record["city"],
        "phone": phone,
        "email": email,
        "received_at": received_at,
        "score": float(score) if score is not None else None,
        "category": category,
        "scoring_status": (
            "legacy_import_scored"
            if score is not None
            else "legacy_import_unscored"
        ),
        "model_type": "legacy_import",
        "config_version": "legacy-json-import-v1",
        "score_components": components,
        "score_reasons": reasons,
        "score_warnings": warnings,
    })
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Import validated records after explicit confirmation",
    )
    args = parser.parse_args()

    load_env_file()
    raw_url = os.environ.get("DATABASE_URL")
    if not raw_url:
        raise SystemExit("DATABASE_URL is missing.")

    url = make_url(raw_url)
    if url.database != "lead_automation":
        raise SystemExit(
            "Refusing to run: DATABASE_URL must target lead_automation."
        )

    if not SOURCE.is_file():
        raise SystemExit("Source leads.json was not found.")

    with SOURCE.open("r", encoding="utf-8") as file:
        records = json.load(file)
    if not isinstance(records, list):
        raise SystemExit("Source must contain a JSON list.")

    conflicts = source_conflicts(records)
    candidates = []
    invalid_indices = []

    for index, record in enumerate(records):
        if index in conflicts:
            continue
        try:
            candidates.append((index, prepare_record(record)))
        except (ValueError, TypeError, OverflowError):
            invalid_indices.append(index)

    engine = create_engine(url, pool_pre_ping=True)
    from app.db.models import LeadRecord

    Session = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    try:
        with Session() as session:
            existing_phones = set(
                session.scalars(select(LeadRecord.phone)).all()
            )
            existing_emails = {
                value.lower()
                for value in session.scalars(
                    select(LeadRecord.email)
                ).all()
            }

        ready = []
        destination_conflicts = 0

        for index, values in candidates:
            phone = values["phone"]
            email_key = values["email"].lower()

            if (
                phone in existing_phones
                or email_key in existing_emails
            ):
                destination_conflicts += 1
                continue

            ready.append((index, values))
            existing_phones.add(phone)
            existing_emails.add(email_key)

        print("=== LEGACY IMPORT REPORT ===")
        print("Source:", SOURCE.name)
        print("Source records:", len(records))
        print("Held for duplicate review:", len(conflicts))
        print("Invalid records:", len(invalid_indices))
        print("Already present/conflicting in database:",
              destination_conflicts)
        print("Ready to import:", len(ready))

        if not args.apply:
            print("DRY RUN: no database records were written.")
            return

        if not ready:
            print("Nothing to import.")
            return

        expected = f"IMPORT {len(ready)}"
        print(f"To proceed, enter exactly: {expected}")
        if input("Confirmation: ").strip() != expected:
            print("Cancelled. No records were written.")
            return

        try:
            with Session() as session:
                session.add_all([
                    LeadRecord(**values)
                    for _, values in ready
                ])
                session.commit()
        except IntegrityError:
            raise SystemExit(
                "Import rolled back because a database constraint "
                "was violated. No partial batch was committed."
            )

        print("Imported records:", len(ready))
        print("Source JSON was not modified.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
