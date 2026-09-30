import json

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


app = FastAPI()


class Lead(BaseModel):
    name: str
    job: str
    city: str
    phone: str
    email: str


def save_lead(new_lead):
    required_fields = ["name", "job", "city", "phone", "email"]

    # Check required fields
    for field in required_fields:
        if field not in new_lead or not new_lead[field]:
            return {
                "success": False,
                "message": f"{field} is missing.",
                "error_type": "validation"
            }

    # Validate phone number
    if (
        not new_lead["phone"].isdigit()
        or len(new_lead["phone"]) != 11
        or not new_lead["phone"].startswith("09")
    ):
        return {
            "success": False,
            "message": "Invalid phone number.",
            "error_type": "validation"
        }

    # Validate email
    if "@" not in new_lead["email"]:
        return {
            "success": False,
            "message": "Invalid email.",
            "error_type": "validation"
        }

    # Read existing leads
    with open("leads.json", "r", encoding="utf-8") as file:
        leads = json.load(file)

    # Check duplicates
    for lead in leads:
        if lead["phone"] == new_lead["phone"]:
            return {
                "success": False,
                "message": "This phone number already exists.",
                "error_type": "duplicate_phone"
            }

        if lead["email"].lower() == new_lead["email"].lower():
            return {
                "success": False,
                "message": "This email already exists.",
                "error_type": "duplicate_email"
            }

    # Save new lead
    leads.append(new_lead)

    with open("leads.json", "w", encoding="utf-8") as file:
        json.dump(leads, file, indent=4)

    return {
        "success": True,
        "message": "Lead saved.",
        "error_type": None
    }


@app.get("/")
def home():
    return {"message": "Lead API is running"}


@app.post("/webhook")
def webhook(lead: Lead):
    result = save_lead(lead.model_dump())

    if result["success"]:
        return result

    if result["error_type"] in ["duplicate_phone", "duplicate_email"]:
        raise HTTPException(
            status_code=409,
            detail=result["message"]
        )

    if result["error_type"] == "validation":
        raise HTTPException(
            status_code=400,
            detail=result["message"]
        )
