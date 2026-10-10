import json
from datetime import datetime, timezone
from pathlib import Path


CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "scoring.json"


def load_scoring_config(config_path=None):
    """Load and validate the scoring configuration."""
    path = Path(config_path) if config_path else CONFIG_PATH

    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    weights = config["score_weights"]
    fit_weight = float(weights["fit"])
    intent_weight = float(weights["intent"])

    if fit_weight < 0 or intent_weight < 0:
        raise ValueError("Score weights cannot be negative.")

    if abs(fit_weight + intent_weight - 1.0) > 1e-9:
        raise ValueError("Fit and intent weights must sum to 1.")

    thresholds = config["thresholds"]
    hot = float(thresholds["hot"])
    warm = float(thresholds["warm"])

    if not 0 <= warm < hot <= 100:
        raise ValueError("Thresholds must satisfy 0 <= warm < hot <= 100.")

    if float(config["fit_points"]["maximum_raw_score"]) <= 0:
        raise ValueError("Maximum fit score must be positive.")

    if float(config["intent_points"]["maximum_raw_score"]) <= 0:
        raise ValueError("Maximum intent score must be positive.")

    if int(config["activity_decay_days"]) <= 0:
        raise ValueError("Activity decay days must be positive.")

    return config


def _normalize(value):
    return str(value).strip().casefold() if value is not None else ""


def _matches(value, options):
    normalized = _normalize(value)
    return bool(normalized) and normalized in {
        _normalize(option) for option in options
    }


def _parse_datetime(value):
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _timeline_days(lead):
    value = lead.get("timeline_days")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if value >= 0 else None

    timeline = _normalize(lead.get("timeline"))

    if timeline in {
        "this_month", "فوری", "همین ماه", "این ماه",
        "within_30_days", "0_30",
    }:
        return 30.0

    if timeline in {
        "next_month", "ماه آینده", "31_90", "within_90_days",
    }:
        return 60.0

    if timeline in {"over_90_days", "بیش از سه ماه", "over_90"}:
        return 120.0

    return None


def score_lead(lead, config=None, now=None):
    """
    Calculate an explainable heuristic priority score.

    This is not a trained model and does not estimate purchase probability.
    A combined score is withheld until the ICP fit profile is configured.
    """
    config = config or load_scoring_config()

    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    now = now.astimezone(timezone.utc)
    reasons = []
    warnings = []

    fit_config = config["fit"]
    fit_points = config["fit_points"]

    target_industries = fit_config["target_industries"]
    adjacent_industries = fit_config["adjacent_industries"]
    company_sizes = fit_config["target_company_sizes"]
    decision_roles = fit_config["decision_maker_roles"]
    influencer_roles = fit_config["influencer_roles"]
    service_regions = fit_config["service_regions"]

    industry_configured = bool(target_industries or adjacent_industries)
    size_configured = bool(company_sizes)
    role_configured = bool(decision_roles or influencer_roles)
    region_configured = bool(service_regions)

    fit_ready = all((
        industry_configured,
        size_configured,
        role_configured,
        region_configured,
    ))

    fit_raw = 0
    fit_max = 0

    if industry_configured:
        fit_max += max(
            float(fit_points["target_industry"]) if target_industries else 0,
            float(fit_points["adjacent_industry"]) if adjacent_industries else 0,
        )

        industry = lead.get("industry")

        if _matches(industry, target_industries):
            fit_raw += float(fit_points["target_industry"])
            reasons.append("Industry matches target market.")
        elif _matches(industry, adjacent_industries):
            fit_raw += float(fit_points["adjacent_industry"])
            reasons.append("Industry matches adjacent market.")
        elif not _normalize(industry):
            reasons.append("Industry is missing; no fit points awarded.")
        else:
            reasons.append(
                "Industry is not in the configured target or adjacent "
                "markets; no fit points awarded."
            )

    if size_configured:
        fit_max += float(fit_points["target_company_size"])

        if _matches(lead.get("company_size"), company_sizes):
            fit_raw += float(fit_points["target_company_size"])
            reasons.append("Company size matches target profile.")
        elif not _normalize(lead.get("company_size")):
            reasons.append("Company size is missing; no fit points awarded.")

    if role_configured:
        fit_max += max(
            float(fit_points["decision_maker"]) if decision_roles else 0,
            float(fit_points["influencer"]) if influencer_roles else 0,
        )

        role = lead.get("contact_role") or lead.get("role")

        if _matches(role, decision_roles):
            fit_raw += float(fit_points["decision_maker"])
            reasons.append("Contact role matches decision-maker profile.")
        elif _matches(role, influencer_roles):
            fit_raw += float(fit_points["influencer"])
            reasons.append("Contact role matches influencer profile.")
        elif not _normalize(role):
            reasons.append("Contact role is missing; no fit points awarded.")

    if region_configured:
        fit_max += float(fit_points["service_region"])

        if _matches(lead.get("service_region"), service_regions):
            fit_raw += float(fit_points["service_region"])
            reasons.append("Service region matches target profile.")
        elif not _normalize(lead.get("service_region")):
            reasons.append("Service region is missing; no fit points awarded.")

    fit_score = None

    if fit_ready and fit_max > 0:
        fit_score = min(100.0, fit_raw / fit_max * 100.0)
    else:
        warnings.append(
            "ICP configuration incomplete: configure industry, company size, "
            "contact role, and service region before classifying leads."
        )

    # Intent signals: budget and expected purchase timeline.
    intent_config = config["intent_points"]
    intent_raw = 0.0
    budget = _normalize(lead.get("budget"))

    if budget in {"yes", "confirmed", "تایید", "تأیید", "verified"}:
        intent_raw += float(intent_config["budget_confirmed"])
        reasons.append("Budget is marked as confirmed.")
    elif budget.isdigit() and int(budget) > 0:
        intent_raw += float(intent_config["budget_amount_provided"])
        reasons.append("A positive budget amount was provided.")
    else:
        reasons.append("No qualifying budget signal was provided.")

    days = _timeline_days(lead)

    if days is not None:
        timeline_points = intent_config["timeline_days"]

        if days <= 30:
            points = float(timeline_points["0_30"])
        elif days <= 90:
            points = float(timeline_points["31_90"])
        else:
            points = float(timeline_points["over_90"])

        intent_raw += points
        reasons.append(f"Purchase timeline signal: {days:g} days.")
    else:
        reasons.append("No qualifying purchase timeline signal was provided.")

    # Recent activities decay linearly to zero at the configured age.
    decay_days = float(config["activity_decay_days"])
    activity_points = intent_config["activities"]
    activities = lead.get("activities", [])

    if not isinstance(activities, list):
        activities = []
        warnings.append("'activities' must be a list; activity scoring skipped.")

    for activity in activities:
        if not isinstance(activity, dict):
            warnings.append("An activity record was invalid and was skipped.")
            continue

        activity_type = str(
            activity.get("type", activity.get("activity_type", ""))
        ).strip()

        base_points = activity_points.get(activity_type)

        if base_points is None:
            warnings.append(f"Unknown activity type skipped: {activity_type!r}.")
            continue

        occurred_at = _parse_datetime(
            activity.get("occurred_at", activity.get("timestamp"))
        )

        if occurred_at is None:
            warnings.append(
                f"Activity {activity_type!r} has no valid timestamp and was skipped."
            )
            continue

        age_days = (now - occurred_at).total_seconds() / 86400

        if age_days < 0:
            warnings.append(
                f"Future activity timestamp skipped: {activity_type!r}."
            )
            continue

        decay_factor = max(0.0, 1.0 - age_days / decay_days)
        contribution = float(base_points) * decay_factor
        intent_raw += contribution

        if contribution > 0:
            reasons.append(
                f"Activity {activity_type!r} contributed "
                f"{contribution:.2f} points after recency decay."
            )
        else:
            reasons.append(
                f"Activity {activity_type!r} is too old to contribute points."
            )

    intent_cap = float(intent_config["maximum_raw_score"])
    intent_raw = min(intent_raw, intent_cap)
    intent_score = intent_raw / intent_cap * 100.0

    # Negative signals reduce the combined heuristic score.
    penalties = {}
    for signal, points in config["negative_points"].items():
        if lead.get(signal) is True:
            penalties[signal] = float(points)
            reasons.append(f"Negative signal applied: {signal}.")

    total_penalty = sum(penalties.values())

    score = None
    category = "unclassified"
    status = "scoring_configuration_incomplete"

    if lead.get("explicit_disqualification") is True:
        status = "disqualified"
        category = "disqualified"
    elif lead.get("invalid_contact") is True:
        status = "needs_review"
        category = "unclassified"
        warnings.append("Contact validity requires review.")
    elif fit_ready and fit_score is not None:
        weights = config["score_weights"]
        combined = (
            fit_score * float(weights["fit"])
            + intent_score * float(weights["intent"])
        )

        score = round(max(0.0, min(100.0, combined - total_penalty)), 2)
        thresholds = config["thresholds"]

        if score >= float(thresholds["hot"]):
            category = "hot"
        elif score >= float(thresholds["warm"]):
            category = "warm"
        else:
            category = "cold"

        status = "scored"

    return {
        "score": score,
        "category": category,
        "scoring_status": status,
        "model_type": "transparent_heuristic",
        "config_version": config["version"],
        "components": {
            "fit_raw": round(fit_raw, 2),
            "fit_max_points": round(fit_max, 2),
            "fit_score": round(fit_score, 2) if fit_score is not None else None,
            "intent_raw": round(intent_raw, 2),
            "intent_cap": round(intent_cap, 2),
            "intent_score": round(intent_score, 2),
            "negative_penalty": round(total_penalty, 2),
            "negative_signals": penalties,
        },
        "reasons": reasons,
        "warnings": warnings,
    }


if __name__ == "__main__":
    example = {
        "name": "Example lead",
        "budget": "confirmed",
        "timeline": "this_month",
        "industry": "marketing agency",
        "company_size": "small",
        "contact_role": "owner",
        "service_region": "iran",
        "activities": [],
    }

    print(json.dumps(score_lead(example), ensure_ascii=False, indent=2))
