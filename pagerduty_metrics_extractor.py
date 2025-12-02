import requests
import json
import csv
from datetime import datetime, timedelta, timezone # Import timezone

PAGERDUTY_API_KEY = "u+nzhLQjt3h9mV2xviKw" # Get this from Configuration -> API Access
# PAGERDUTY_SUBDOMAIN = "rakpd.pagerduty.com" #YOUR_SUBDOMAIN e.g., yourcompany.pagerduty.com

HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Token token={PAGERDUTY_API_KEY}",
    "Content-Type": "application/json",
    "From": "ts-romuluscalu.nalus@rakuten.com" # PagerDuty recommends setting a 'From' header
}

BASE_URL = f"https://api.pagerduty.com"

# --- Configuration for filtering ---
# Add the IDs of the teams you want to filter by.
# Example: PAGERDUTY_TEAM_IDS = ["T1234567890ABCDEF", "TFEDCBA0987654321"]
PAGERDUTY_TEAM_IDS = [] # Keep empty list if no team filter is desired

# Add the IDs of the services you want to filter by.
# Example: PAGERDUTY_SERVICE_IDS = ["P1234567890ABCDEF", "PFEDCBA0987654321"]
PAGERDUTY_SERVICE_IDS = ["PJ9IYQT"] # Corrected: The Service ID is a string, replace with your actual ID(s)
# --- END Configuration ---


def get_incidents(since, until, team_ids=None, service_ids=None):
    all_incidents = []
    offset = 0
    limit = 100 # Max limit per request

    if team_ids is None:
        team_ids = []
    if service_ids is None:
        service_ids = []

    # Prepare params with filters
    params = {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "statuses[]": ["resolved"], # Filter statuses if needed
        "sort_by": "created_at:asc",
        "offset": offset,
        "limit": limit
    }

    if team_ids:
        params["team_ids[]"] = team_ids
    if service_ids:
        params["service_ids[]"] = service_ids

    # --- DEBUG PRINTS START for get_incidents ---
    print(f"--- Debugging get_incidents API Call ---")
    print(f"Request URL: {BASE_URL}/incidents")
    print(f"Request Headers: {HEADERS}")
    print(f"Request Parameters: {params}")
    # --- END DEBUG PRINTS ---

    while True:
        response = requests.get(f"{BASE_URL}/incidents", headers=HEADERS, params=params)
        response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)

        data = response.json() # First, parse the JSON response into a Python dictionary

        # --- DEBUG PRINTS START for get_incidents ---
        print(f"API Response Status Code: {response.status_code}")
        print(f"API Response Data (first 500 chars): {json.dumps(data, indent=2)[:500]}...")
        print(f"Number of incidents received in this page: {len(data.get('incidents', []))}")
        print(f"PagerDuty 'more' flag: {data.get('more')}")
        # --- END DEBUG PRINTS ---

        incidents = data.get("incidents", []) # Then, get the list of incidents from the dictionary

        all_incidents.extend(incidents)

        if not data.get("more"): # Check 'more' from the parsed dictionary
            break

        offset += limit
        params["offset"] = offset # Update offset for subsequent requests for pagination
    return all_incidents


def get_incident_notes(incident_id):
    notes = []
    offset = 0
    limit = 100
    while True:
        params = {
            "offset": offset,
            "limit": limit,
            "is_overview": "false" # Ensure full log entries
        }
        response = requests.get(f"{BASE_URL}/incidents/{incident_id}/log_entries", headers=HEADERS, params=params)

        response.raise_for_status()

        data = response.json()

        log_entries = data.get("log_entries", [])

        for entry in log_entries:
            if entry.get("type") == "annotate_log_entry":
                notes.append(entry.get("channel", {}).get("summary", "")) # Correctly extract note from 'summary'

        if not data.get("more"):
            break

        offset += limit
        params["offset"] = offset # Update offset for subsequent requests for pagination
    return "\n--- NOTE ---\n".join(notes) # Join multiple notes for an incident


def main():
    # --- MODIFIED: Incidents specifically for the month of October 2025 (UTC) ---
    # Define the start of October 2025 in UTC
    since = datetime(2025, 10, 1, 0, 0, 0, tzinfo=timezone.utc)

    # Define the end of October 2025 (i.e., the start of November 1st, 2025) in UTC
    until = datetime(2025, 11, 1, 0, 0, 0, tzinfo=timezone.utc)

    print(f"Reporting period (UTC): {since} to {until}")
    # --- END MODIFIED ---

    incidents = get_incidents(
        since,
        until,
        team_ids=PAGERDUTY_TEAM_IDS,
        service_ids=PAGERDUTY_SERVICE_IDS
    )

    print(f"Found {len(incidents)} incidents.")

    output_data = []
    csv_headers = [
        "Incident Number",
        "Incident UUID",
        "Title", "Service", "Status", "Created At",
        "Resolved At", "Assigned To", "Urgency", "Notes"
    ]

    for incident in incidents:
        incident_id = incident.get("id")
        incident_number = incident.get("incident_number")

        incident_notes = get_incident_notes(incident_id)

        assigned_to_list = []
        if incident.get("assignments"):
            assigned_to_list = [assignee.get("summary", "") for assignee in incident.get("assignments", [])]
        assigned_to = ", ".join(assigned_to_list)

        output_data.append({
            "Incident Number": incident_number,
            "Incident UUID": incident_id,
            "Title": incident.get("title"),
            "Urgency": incident.get("urgency"),
            "Service": incident.get("service", {}).get("summary"),
            "Created At": incident.get("created_at"),
            "Status": incident.get("status"),
            "Resolved At": incident.get("resolved_at"),
            "Assigned To": assigned_to,
            "Notes": incident_notes
        })

    filename = f"pagerduty_incidents_october_2025_utc.csv" # Updated filename to reflect UTC
    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
        writer.writeheader()
        writer.writerows(output_data)
    print(f"Report saved to {filename}")

if __name__ == "__main__":
    main()
