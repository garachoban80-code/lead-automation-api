from typing import Literal

from pydantic import BaseModel, ConfigDict


class Lead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    job: str
    city: str
    phone: str
    email: str

    # Optional fields used to assess ideal-customer fit.
    industry: str | None = None
    company_size: str | None = None
    contact_role: str | None = None
    service_region: str | None = None


class QualifiedLead(Lead):
    budget: str
    timeline: str
    need: str


class LeadActivityInput(BaseModel):
    """Allow only recognized activity types from a trusted caller."""

    model_config = ConfigDict(extra="forbid")

    type: Literal[
        "demo_booked",
        "quote_requested",
        "contact_form_submitted",
        "sales_email_reply",
        "pricing_page_view",
    ]
