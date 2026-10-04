
import json


def score_lead(lead):
    score = 0
    reasons = []

    # Check budget
    if lead.get("budget") == "yes":
        score += 40
        reasons.append("Budget is available")
    else:
        reasons.append("Budget is not confirmed")

    # Check timeline
    if lead.get("timeline") == "this_month":
        score += 25
        reasons.append("Ready to start this month")
    else:
        score += 10
        reasons.append("Timeline is not confirmed")

    # Check need
    if lead.get("need") == "clear":
        score += 35
        reasons.append("Customer need is clear")
    else:
        score += 15
        reasons.append("Customer need needs clarification")

    # Determine category
    if score >= 70:
        category = "hot"
    elif score >= 40:
        category = "warm"
    else:
        category = "cold"

    return {
        "score": score,
        "category": category,
        "reasons": reasons
    }


if __name__ == "__main__":

    customers = [
        {
            "name": "Ali",
            "budget": "yes",
            "timeline": "this_month",
            "need": "clear"
        },
        {
            "name": "Sara",
            "budget": "no",
            "timeline": "uncertain",
            "need": "unclear"
        },
        {
            "name": "Reza",
            "budget": "yes",
            "timeline": "uncertain",
            "need": "clear"
        }
    ]

    for customer in customers:
        result = score_lead(customer)

        customer["score"] = result["score"]
        customer["category"] = result["category"]
        customer["reasons"] = result["reasons"]

        print(customer)
        print("--------------------")

    with open(
        "qualified_leads.json",
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            customers,
            file,
            ensure_ascii=False,
            indent=4
        )

    print("Qualified leads saved successfully.")
