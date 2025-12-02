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

    while True:
        response = requests.get(f"{BASE_URL}/incidents", headers=HEADERS, params=params)
        response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)

        data = response.json() # First, parse the JSON response into a Python dictionary

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

        # --- DEBUG PRINT STATEMENTS START ---
        print(f"--- Debugging notes for Incident ID: {incident_id} ---")
        print(f"API Request URL: {response.url}") # Show the actual URL called
        print(f"API Response Status: {response.status_code}")
        print(f"Log entries fetched for this page: {len(log_entries)}")
        for i, entry in enumerate(log_entries):
            print(f"  Entry {i+1} Type: {entry.get('type')}")
            if entry.get("type") == "annotate_log_entry":
                content = entry.get('channel', {}).get('content', 'No content found')
                print(f"    Found annotate_log_entry. Content: {content[:100]}...") # Print first 100 chars
            # Uncomment the line below for a full dump of each log entry if needed
            # print(f"  Full Entry {i+1}: {json.dumps(entry, indent=2)}")
        print(f"More log entries for this incident? {data.get('more')}")
        # --- DEBUG PRINT STATEMENTS END ---

        for entry in log_entries:
            if entry.get("type") == "annotate_log_entry":
                notes.append(entry.get("channel", {}).get("content", "")) # The note content

        if not data.get("more"):
            break

        offset += limit
        params["offset"] = offset # Update offset for subsequent requests for pagination
    return "\n--- NOTE ---\n".join(notes) # Join multiple notes for an incident


def main():
    # Example: Incidents from the last 7 days.
    until = datetime.now(timezone.utc)
    since = until - timedelta(days=7)

    incidents = get_incidents(
        since,
        until,
        team_ids=PAGERDUTY_TEAM_IDS,
        service_ids=PAGERDUTY_SERVICE_IDS
    )

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

        # Handle potential missing 'assignments' key
        assigned_to_list = []
        if incident.get("assignments"):
            assigned_to_list = [assignee.get("summary", "") for assignee in incident.get("assignments", [])]
        assigned_to = ", ".join(assigned_to_list)


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
