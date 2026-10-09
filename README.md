# Lead Automation API

A lead management and automation project built with **Python, FastAPI, and n8n**. It receives lead information, validates customer data, scores qualified leads, and provides statistical reports through an API.

## Features

- Receive leads through REST API endpoints
- Validate required fields, email addresses, and Iranian mobile numbers
- Detect duplicate phone numbers and email addresses
- Score qualified leads based on budget, timeline, and clarity of need
- Categorize leads as **Hot**, **Warm**, or **Cold**
- Store lead records in PostgreSQL using SQLAlchemy
- Generate statistical reports with lead counts and percentages
- Integrate with n8n workflows
- Support automated Telegram notifications through n8n

## Architecture

```text
Lead Source
    |
    v
n8n Webhook
    |
    v
FastAPI
    |
    +--> Validate Lead
    |
    +--> Check Duplicates
    |
    +--> Score Qualified Lead
    |
    +--> Store Lead Data
    |
    v
API Response

n8n Report Workflow
    |
    v
FastAPI /report
    |
    v
Telegram Report
```

## API Endpoints

### 1. POST `/webhook`

Receives and validates standard lead information.

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

### 2. POST `/qualified-lead`

Receives lead information with additional qualification fields and calculates a score and category.

Example request:

```json
{
  "name": "Test Customer",
  "job": "Automation Test",
  "city": "Test City",
  "phone": "09120000000",
  "email": "test-qualified@example.com",
  "budget": "yes",
  "timeline": "this_month",
  "need": "clear"
}
```

The scoring system considers:
- Budget availability
- Project timeline
- Clarity of customer requirements

### 3. GET `/report`

Returns statistical information about stored leads, including:
- Total leads
- Hot, Warm, and Cold leads
- Unclassified leads
- Lead category percentages

## Technologies

- Python
- FastAPI
- Pydantic
- Uvicorn
- Requests
- n8n
- REST API
- JSON
- Telegram Bot integration through n8n

## Installation

Clone the repository:

```bash
git clone https://github.com/garachoban80-code/lead-automation-api.git
cd lead-automation-api
```

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run the API

```bash
uvicorn lead_api:app --host 127.0.0.1 --port 8000 --reload
```

API base URL:

`http://127.0.0.1:8000`

Interactive API documentation:

`http://127.0.0.1:8000/docs`

## n8n Integration

The API can be connected to n8n using Webhook and HTTP Request nodes. Workflows can forward incoming lead information to FastAPI, process the response, route leads based on category, and send notifications through Telegram.

A separate report workflow can request `/report` and deliver the statistics to Telegram.

## Data and Security

Lead records are stored in PostgreSQL. Legacy JSON files may contain customer data; keep them out of public repositories.

Do not publish API keys, bot tokens, passwords, or real customer information.

## Project Status

The lead intake, qualification, reporting, and n8n integration workflows have been tested in a local development environment.

## Author

Portfolio project focused on Python API development, workflow automation, data validation, and lead qualification.
