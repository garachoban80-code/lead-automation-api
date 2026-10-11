from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.database import SessionLocal
from app.db.models import LeadActivity, LeadRecord, LeadScoreHistory
from app.services.scoring_service import score_lead


REQUIRED_FIELDS = ("name", "job", "city", "phone", "email")

LEAD_FIELDS = (
    "name",
    "job",
    "city",
    "phone",
    "email",
    "industry",
    "company_size",
    "contact_role",
    "service_region",
    "budget",
    "timeline",
    "need",
    "received_at",
    "score",
    "category",
    "scoring_status",
    "model_type",
    "config_version",
)


def _failure(message, error_type):
    return {
        "success": False,
        "message": message,
        "error_type": error_type,
    }


def _add_score_history(session, lead, event_type, activity_id=None):
    """Snapshot a lead's current scoring state in the same transaction."""
    history = LeadScoreHistory(
        lead_id=lead.id,
        activity_id=activity_id,
        event_type=event_type,
        score=lead.score,
        category=lead.category,
        scoring_status=lead.scoring_status,
        model_type=lead.model_type,
        config_version=lead.config_version,
        score_components=lead.score_components,
        score_reasons=lead.score_reasons,
        score_warnings=lead.score_warnings,
    )
    session.add(history)
    return history


def _parse_received_at(value):
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(
                value.strip().replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise ValueError("Invalid received_at timestamp.") from exc
    else:
        raise ValueError("Invalid received_at timestamp.")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _record_to_dict(record):
    data = {
        field: getattr(record, field)
        for field in REQUIRED_FIELDS
    }

    for field in (
        "industry",
        "company_size",
        "contact_role",
        "service_region",
        "budget",
        "timeline",
        "need",
    ):
        value = getattr(record, field)
        if value is not None:
            data[field] = value

    data.update({
        "score": record.score,
        "category": record.category,
        "scoring_status": record.scoring_status,
    })

    if record.received_at is not None:
        data["received_at"] = record.received_at.isoformat()

    if record.model_type is not None:
        data["model_type"] = record.model_type

    if record.config_version is not None:
        data["config_version"] = record.config_version

    if record.score_components is not None:
        data["components"] = record.score_components

    if record.score_reasons is not None:
        data["reasons"] = record.score_reasons

    if record.score_warnings is not None:
        data["warnings"] = record.score_warnings

    return data


def load_leads():
    """Load all leads from PostgreSQL."""
    with SessionLocal() as session:
        records = session.scalars(
            select(LeadRecord).order_by(LeadRecord.id)
        ).all()

        return [_record_to_dict(record) for record in records]


def save_lead(new_lead):
    """Validate and save one lead to PostgreSQL."""
    if not isinstance(new_lead, dict):
        return _failure("Lead must be an object.", "validation")

    for field in REQUIRED_FIELDS:
        value = new_lead.get(field)
        if not isinstance(value, str) or not value.strip():
            return _failure(f"{field} is missing.", "validation")

    phone = new_lead["phone"].strip()
    email = new_lead["email"].strip()

    if not phone.isdigit() or len(phone) != 11 or not phone.startswith("09"):
        return _failure("Invalid phone number.", "validation")

    if "@" not in email:
        return _failure("Invalid email.", "validation")

    values = {
        field: new_lead[field]
        for field in LEAD_FIELDS
        if field in new_lead
    }
    values["phone"] = phone
    values["email"] = email

    try:
        if "received_at" in values:
            values["received_at"] = _parse_received_at(
                values["received_at"]
            )
    except ValueError as exc:
        return _failure(str(exc), "validation")

    values["score_components"] = new_lead.get(
        "score_components", new_lead.get("components")
    )
    values["score_reasons"] = new_lead.get(
        "score_reasons", new_lead.get("reasons")
    )
    values["score_warnings"] = new_lead.get(
        "score_warnings", new_lead.get("warnings")
    )

    with SessionLocal() as session:
        existing_phone = session.scalar(
            select(LeadRecord.id).where(LeadRecord.phone == phone).limit(1)
        )
        if existing_phone is not None:
            return _failure(
                "This phone number already exists.",
                "duplicate_phone",
            )

        existing_email = session.scalar(
            select(LeadRecord.id)
            .where(func.lower(LeadRecord.email) == email.lower())
            .limit(1)
        )
        if existing_email is not None:
            return _failure(
                "This email already exists.",
                "duplicate_email",
            )

        record = LeadRecord(**values)
        session.add(record)

        try:
            session.flush()
            _add_score_history(session, record, "lead_created")
            session.commit()
        except IntegrityError as exc:
            session.rollback()

            diagnostic = getattr(exc.orig, "diag", None)
            constraint_name = getattr(
                diagnostic, "constraint_name", None
            )

            if constraint_name == "uq_leads_phone":
                return _failure(
                    "This phone number already exists.",
                    "duplicate_phone",
                )

            if constraint_name == "uq_leads_email_lower":
                return _failure(
                    "This email already exists.",
                    "duplicate_email",
                )

            raise

    return {
        "success": True,
        "message": "Lead saved.",
        "error_type": None,
        "lead_id": record.id,
    }


def save_activity(lead_id: int, activity_type: str):
    """Persist an activity and atomically recalculate the lead score."""
    with SessionLocal() as session:
        lead = session.scalar(
            select(LeadRecord)
            .where(LeadRecord.id == lead_id)
            .with_for_update()
        )

        if lead is None:
            return _failure("Lead not found.", "lead_not_found")

        activity = LeadActivity(
            lead_id=lead_id,
            type=activity_type,
            occurred_at=datetime.now(timezone.utc),
        )
        session.add(activity)

        try:
            session.flush()

            activities = session.scalars(
                select(LeadActivity)
                .where(LeadActivity.lead_id == lead_id)
                .order_by(LeadActivity.occurred_at, LeadActivity.id)
            ).all()

            lead_data = _record_to_dict(lead)
            lead_data["activities"] = [
                {
                    "type": item.type,
                    "occurred_at": item.occurred_at.isoformat(),
                }
                for item in activities
            ]

            scoring = score_lead(lead_data)
            lead.score = scoring["score"]
            lead.category = scoring["category"]
            lead.scoring_status = scoring["scoring_status"]
            lead.model_type = scoring["model_type"]
            lead.config_version = scoring["config_version"]
            lead.score_components = scoring["components"]
            lead.score_reasons = scoring["reasons"]
            lead.score_warnings = scoring["warnings"]

            _add_score_history(
                session,
                lead,
                "activity_recorded",
                activity_id=activity.id,
            )

            session.commit()
            session.refresh(activity)
        except Exception:
            session.rollback()
            raise

        return {
            "success": True,
            "message": "Activity saved and lead rescored.",
            "error_type": None,
            "activity_id": activity.id,
            "lead_id": activity.lead_id,
            "type": activity.type,
            "occurred_at": activity.occurred_at.isoformat(),
            "score": lead.score,
            "category": lead.category,
            "scoring_status": lead.scoring_status,
        }
