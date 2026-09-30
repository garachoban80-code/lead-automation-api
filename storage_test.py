import json


def save_lead(new_lead):

    required_fields = ["name", "job", "city", "phone", "email"]

    for field in required_fields:
        if field not in new_lead or not new_lead[field]:
            return f"{field} is missing."

        if not new_lead["phone"].isdigit() or len(new_lead["phone"]) != 11:
            return "Invalid phone number."

        if "@" not in new_lead["email"]:
            return "Invalid email."

    with open("leads.json", "r") as file:
        leads = json.load(file)

    for lead in leads:
        if lead["phone"] == new_lead["phone"]:
            return "This lead already exists."

    leads.append(new_lead)

    with open("leads.json", "w") as file:
        json.dump(leads, file, indent=4)

    return "Lead saved."


new_lead = {
    "name": "Omid",
    "job": "restaurant",
    "city": "Tehran",
    "phone": "09123456789",
    "email": "omidexample.com"
}

result = save_lead(new_lead)

print(result)
