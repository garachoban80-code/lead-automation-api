# Lead Automation API

A simple lead collection and validation API built with **FastAPI** and integrated with **n8n**.

## Project Overview

This project is a small automation system for receiving, validating, and storing customer leads.

The system receives lead data through an **n8n Webhook**, sends the data to a **FastAPI** endpoint, validates the information, checks for duplicate phone numbers and email addresses, and stores valid leads in a JSON file.

## Architecture

Client
   ↓
n8n Webhook
   ↓
n8n HTTP Request
   ↓
FastAPI
   ↓
Validation
   ↓
Duplicate Check
   ↓
leads.json
   ↓
HTTP Response

## Technologies

- Python
- FastAPI
- Pydantic
- Requests
- n8n
- JSON
- HTTP / REST API

## Features

- Receive lead data through an API endpoint
- Validate required fields
- Validate Iranian phone numbers
- Basic email validation
- Detect duplicate phone numbers
- Detect duplicate email addresses
- Return appropriate HTTP status codes
- Store leads in JSON format
- Integrate with n8n automation workflows

## API Endpoint

### POST `/webhook`

Example request:

```json
{
  "name": "Ali Ahmadi",
  "job": "Web Developer",
  "city": "Tehran",
  "phone": "09123456789",
  "email": "ali@example.com"
}
```

## Response Examples

### Successful Request

HTTP 200 OK

```json
{
  "success": true,
  "message": "Lead saved.",
  "error_type": null
}
```

### Validation Error

HTTP 400 Bad Request

```json
{
  "success": false,
  "message": "Invalid phone number."
}
```

### Duplicate Phone or Email

HTTP 409 Conflict

```json
{
  "success": false,
  "message": "This phone number already exists."
}
```

or:

```json
{
  "success": false,
  "message": "This email already exists."
}
```

## Project Structure

lead-automation-api/
│
├── lead_api.py
├── send_test.py
├── storage_test.py
├── leads.example.json
├── requirements.txt
├── .gitignore
└── README.md

## Installation

Clone the repository:

```bash
git clone <repository-url>
cd lead-automation-api
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate the virtual environment.

### Linux / macOS

```bash
source .venv/bin/activate
```

### Windows

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the API

Start FastAPI with Uvicorn:

```bash
uvicorn lead_api:app --reload
```

The API will be available at:

http://127.0.0.1:8000

Interactive API documentation:

http://127.0.0.1:8000/docs

## n8n Integration

The API can be connected to an n8n workflow using an HTTP Request node.

Example workflow:

Webhook
   ↓
HTTP Request
   ↓
FastAPI
   ↓
Response

n8n receives the lead through a Webhook and forwards the lead data to the FastAPI `/webhook` endpoint.

## HTTP Status Codes

| Status Code | Meaning |
|---|---|
| 200 | Lead successfully saved |
| 400 | Validation or business rule error |
| 409 | Duplicate phone number or email |
| 422 | Invalid request structure |

## Security Note

Real lead data should not be committed to a public repository.

The real `leads.json` file is excluded using `.gitignore`.

`leads.example.json` is provided as a safe example file.

## Future Improvements

- AI-based lead qualification
- Lead scoring
- Database integration
- CRM integration
- Automated notifications
- Automated follow-up
- AI Agent integration
- PostgreSQL
- Authentication
- Docker deployment

## Author

Personal portfolio project focused on **Python, APIs, n8n automation, and AI-powered business automation**.
