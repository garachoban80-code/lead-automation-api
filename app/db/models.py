from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class LeadRecord(Base):
    __tablename__ = "leads"

    __table_args__ = (
        UniqueConstraint("phone", name="uq_leads_phone"),
        Index("uq_leads_email_lower", text("lower(email)"), unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    job: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)

    industry: Mapped[str | None] = mapped_column(String(120))
    company_size: Mapped[str | None] = mapped_column(String(80))
    contact_role: Mapped[str | None] = mapped_column(String(120))
    service_region: Mapped[str | None] = mapped_column(String(120))

    budget: Mapped[str | None] = mapped_column(String(100))
    timeline: Mapped[str | None] = mapped_column(String(100))
    need: Mapped[str | None] = mapped_column(Text)

    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    score: Mapped[float | None] = mapped_column(Float)
    category: Mapped[str] = mapped_column(
        String(30), nullable=False, default="unclassified"
    )
    scoring_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="unclassified"
    )
    model_type: Mapped[str | None] = mapped_column(String(50))
    config_version: Mapped[str | None] = mapped_column(String(80))

    score_components: Mapped[dict | None] = mapped_column(JSON)
    score_reasons: Mapped[list | None] = mapped_column(JSON)
    score_warnings: Mapped[list | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    activities: Mapped[list["LeadActivity"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class LeadActivity(Base):
    __tablename__ = "lead_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    type: Mapped[str] = mapped_column(String(100), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    details: Mapped[dict | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    lead: Mapped["LeadRecord"] = relationship(back_populates="activities")

class LeadScoreHistory(Base):
    __tablename__ = "lead_score_history"

    __table_args__ = (
        Index(
            "ix_lead_score_history_lead_created",
            "lead_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
    )
    activity_id: Mapped[int | None] = mapped_column(
        ForeignKey("lead_activities.id", ondelete="SET NULL"),
        nullable=True,
    )

    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    scoring_status: Mapped[str] = mapped_column(String(50), nullable=False)
    model_type: Mapped[str | None] = mapped_column(String(50))
    config_version: Mapped[str | None] = mapped_column(String(80))

    score_components: Mapped[dict | None] = mapped_column(JSON)
    score_reasons: Mapped[list | None] = mapped_column(JSON)
    score_warnings: Mapped[list | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
