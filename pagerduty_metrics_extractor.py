import requests
import json
import csv
from datetime import datetime, timedelta, timezone

PAGERDUTY_API_KEY = "u+nzhLQjt3h9mV2xviKw" # Get this from Configuration -> API Access
# PAGERDUTY_SUBDOMAIN = "rakpd.pagerduty.com" #YOUR_SUBDOMAIN e.g., yourcompany.pagerduty.com

HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Token token={PAGERDUTY_API_KEY}",
    "Content-Type": "application/json",
    "From": "ts-romuluscalu.nalus@rakuten.com" # PagerDuty recommends setting a 'From' header
}

BASE_URL = f"https://api.pagerduty.com"

# --- NEW: Configuration for filtering ---
# Add the IDs of the teams you want to filter by.
# Example: PAGERDUTY_TEAM_IDS = ["T1234567890ABCDEF", "TFEDCBA0987654321"]
PAGERDUTY_TEAM_IDS = [] # Keep empty list if no team filter is desired

# Add the IDs of the services you want to filter by.
# Example: PAGERDUTY_SERVICE_IDS = ["P1234567890ABCDEF", "PFEDCBA0987654321"]
PAGERDUTY_SERVICE_IDS = [] # Keep empty list if no service filter is desired
# --- END NEW ---

def get_incidents(since, until, team_ids=None, service_ids=None): # Added team_ids and service_ids parameters
    all_incidents = []
    offset = 0
    limit = 100 # Max limit per request

    # --- MODIFIED: Add filters to params ---
    if service_ids is None:
        service_ids = [PJ9IYQT]

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
    # --- END MODIFIED ---

    while True:
        response = requests.get(f"{BASE_URL}/incidents", headers=HEADERS, params=params)

        response.raise_for_status()

        data = response.get("incidents", [])

        incidents = data.get("incidents", [])

        all_incidents.extend(incidents)

        if not data.get("more"):
            break

        offset += limit
        params["offset"] = offset # Update offset for subsequent requests
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
                notes.append(entry.get("channel", {}).get("content", "")) # The note content

        if not data.get("more"):
            break

        offset += limit
        # Update offset for subsequent requests (if there are more pages of notes)
        params["offset"] = offset
    return "\n--- NOTE ---\n".join(notes) # Join multiple notes for an incident

def main():
    # Example: Incidents from the last 1 day.
    until = datetime.now(timezone.utc)
    since = until - timedelta(days=1)

    # --- MODIFIED: Pass filters to get_incidents ---
    incidents = get_incidents(
        since,
        until,
        team_ids=PAGERDUTY_TEAM_IDS,
        service_ids=PAGERDUTY_SERVICE_IDS
    )
    # --- END MODIFIED ---

    print(f"Found {len(incidents)} incidents.")

    output_data = []
    # Define the fields for your CSV, including a custom 'Notes' field
    csv_headers = [
        "Incident ID", "Title", "Service", "Status", "Created At",
        "Resolved At", "Assigned To", "Urgency", "Notes"
    ]

    for incident in incidents:
        incident_id = incident.get("id")
        incident_notes = get_incident_notes(incident_id) # Fetch notes for each incident
        assigned_to = ", ".join([assignee.get("summary", "") for assignee in incident.get("assignments", [])])
        output_data.append({
            "Incident ID": incident_id,
            "Title": incident.get("title"),
            "Urgency": incident.get("urgency"),
            "Service": incident.get("service", {}).get("summary"),
            "Created At": incident.get("created_at"),
            "Status": incident.get("status"),
            "Resolved At": incident.get("resolved_at"),
            "Assigned To": assigned_to,
            "Notes": incident_notes
        })

    # Write to CSV
    with open("pagerduty_incidents_with_notes.csv", "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
        writer.writeheader()
        writer.writerows(output_data)
    print(f"Report saved to pagerduty_incidents_with_notes.csv")

if __name__ == "__main__":
    main()
