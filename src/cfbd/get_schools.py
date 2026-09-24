import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


# Load environment variables from .env
load_dotenv()

API_KEY = os.getenv("CFBD_API_KEY")

if not API_KEY:
    raise ValueError(
        "CFBD_API_KEY was not found. "
        "Make sure it is set in your .env file."
    )


# CFBD API configuration
BASE_URL = "https://api.collegefootballdata.com"
ENDPOINT = "/teams"

headers = {
    "Authorization": f"Bearer {API_KEY}"
}


# Request school/team data
response = requests.get(
    f"{BASE_URL}{ENDPOINT}",
    headers=headers,
    timeout=30,
)

# Raise an error if the API request failed
response.raise_for_status()

schools = response.json()


# Determine repository root
project_root = Path(__file__).resolve().parents[2]

output_path = project_root / "data" / "raw" / "schools" / "cfbd_teams.json"

output_path.parent.mkdir(parents=True, exist_ok=True)


# Save the raw API response
with output_path.open("w", encoding="utf-8") as file:
    json.dump(schools, file, indent=2)


print(f"Successfully retrieved {len(schools)} teams.")
print(f"Saved to: {output_path}")
