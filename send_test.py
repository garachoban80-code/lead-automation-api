import requests

data = {
    "name": "Hamid",
    "job": "Freelancer",
    "city": "Ardabil",
    "phone": "09123456784",
    "email": "ali@example.com"
}

response = requests.post(
    "http://localhost:5678/webhook-test/lead",
    json=data
)

print(response.status_code)
print("STATUS:", response.status_code)
print("TEXT:", repr(response.text))
