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
