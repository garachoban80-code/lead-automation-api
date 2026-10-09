
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
from app.models.lead import Lead, QualifiedLead

from app.services.scoring_service import score_lead
from app.db.repository import load_leads, save_lead
from app.security.api_key import require_api_key


app = FastAPI(title="Lead Automation API")

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
def webhook(lead: Lead, _: None = Depends(require_api_key)):
    result = save_lead(lead.model_dump(mode="json", exclude_none=True))
    return handle_result(result)


@app.post("/qualified-lead")
def qualified_lead(lead: QualifiedLead, _: None = Depends(require_api_key)):
    data = lead.model_dump(mode="json", exclude_none=True)

    data["received_at"] = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )

    data.update(score_lead(data))

    result = save_lead(data)
    handle_result(result)

    return {
        "success": True,
        "message": "Lead saved and scored.",
        "lead_id": result["lead_id"],
        "lead": data,
    }


@app.get("/report")
def report(_: None = Depends(require_api_key)):
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
