
import json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from lead_scoring import score_lead


app = FastAPI(title="Lead Automation API")

DATA_FILE = Path("leads.json")


class Lead(BaseModel):
    name: str
    job: str
    city: str
    phone: str
    email: str


class QualifiedLead(Lead):
    budget: str
    timeline: str
    need: str


def load_leads():
    """Load leads from JSON or return an empty list if the file is missing."""
    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            leads = json.load(file)

        if not isinstance(leads, list):
            raise ValueError("Lead data must be a JSON list.")

        return leads

    except FileNotFoundError:
        return []


def save_leads(leads):
    """Save all leads to the JSON data file."""
    with DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(leads, file, ensure_ascii=False, indent=4)


def save_lead(new_lead):
    """Validate a lead, check duplicates, and store it."""
    required_fields = ["name", "job", "city", "phone", "email"]

    for field in required_fields:
        if not new_lead.get(field):
            return {
                "success": False,
                "message": f"{field} is missing.",
                "error_type": "validation",
            }

    phone = new_lead["phone"]
    email = new_lead["email"]

    if (
        not phone.isdigit()
        or len(phone) != 11
        or not phone.startswith("09")
    ):
        return {
            "success": False,
            "message": "Invalid phone number.",
            "error_type": "validation",
        }

    if "@" not in email:
        return {
            "success": False,
            "message": "Invalid email.",
            "error_type": "validation",
        }

    leads = load_leads()

    for lead in leads:
        if lead.get("phone") == phone:
            return {
                "success": False,
                "message": "This phone number already exists.",
                "error_type": "duplicate_phone",
            }

        existing_email = lead.get("email", "")
        if existing_email.lower() == email.lower():
            return {
                "success": False,
                "message": "This email already exists.",
                "error_type": "duplicate_email",
            }

    leads.append(new_lead)
    save_leads(leads)

    return {
        "success": True,
        "message": "Lead saved.",
        "error_type": None,
    }


def handle_result(result):
    """Convert validation and duplicate errors into HTTP responses."""
    if result["success"]:
        return result

    if result["error_type"] in [
        "duplicate_phone",
        "duplicate_email",
    ]:
        raise HTTPException(
            status_code=409,
            detail=result["message"],
        )

    raise HTTPException(
        status_code=400,
        detail=result["message"],
    )


@app.get("/")
def home():
    return {"message": "Lead API is running"}


@app.post("/webhook")
def webhook(lead: Lead):
    result = save_lead(lead.model_dump())
    return handle_result(result)


@app.post("/qualified-lead")
def qualified_lead(lead: QualifiedLead):
    data = lead.model_dump()

    data["received_at"] = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )

    data.update(score_lead(data))

    result = save_lead(data)
    handle_result(result)

    return {
        "success": True,
        "message": "Lead saved and scored.",
        "lead": data,
    }


@app.get("/report")
def report():
    leads = load_leads()

    hot_count = 0
    warm_count = 0
    cold_count = 0

    for lead in leads:
        if lead.get("category") == "hot":
            hot_count += 1
        elif lead.get("category") == "warm":
            warm_count += 1
        elif lead.get("category") == "cold":
            cold_count += 1

    total_leads = len(leads)
    classified_leads = hot_count + warm_count + cold_count
    unclassified = total_leads - classified_leads

    if total_leads > 0:
        hot_percentage = hot_count / total_leads * 100
        warm_percentage = warm_count / total_leads * 100
        cold_percentage = cold_count / total_leads * 100
        unclassified_percentage = unclassified / total_leads * 100
        classified_percentage = classified_leads / total_leads * 100
    else:
        hot_percentage = 0
        warm_percentage = 0
        cold_percentage = 0
        unclassified_percentage = 0
        classified_percentage = 0

    if classified_leads > 0:
        hot_percentage_of_classified = (
            hot_count / classified_leads * 100
        )
    else:
        hot_percentage_of_classified = 0

    return {
        "total_leads": total_leads,
        "hot": hot_count,
        "warm": warm_count,
        "cold": cold_count,
        "unclassified": unclassified,
        "classified_leads": classified_leads,
        "hot_percentage": round(hot_percentage, 2),
        "warm_percentage": round(warm_percentage, 2),
        "cold_percentage": round(cold_percentage, 2),
        "unclassified_percentage": round(
            unclassified_percentage, 2
        ),
        "classified_leads_percentage": round(
            classified_percentage, 2
        ),
        "hot_percentage_of_classified": round(
            hot_percentage_of_classified, 2
        ),
    }
