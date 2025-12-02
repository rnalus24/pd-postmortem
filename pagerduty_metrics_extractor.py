import requests
import json
import csv
from datetime import datetime, timedelta, timezone
import pytz # Re-introducing pytz for JST conversion

# PAGERDUTY_API_KEY = "u+nzhLQjt3h9mV2xviKw" # Get this from Configuration -> API Access
if len(sys.argv) < 2:
    print("Error: PagerDuty API Key not provided as a command-line argument.")
    sys.exit(1) # Exit with an error code
PAGERDUTY_API_KEY = sys.argv[1]
# PAGERDUTY_SUBDOMAIN = "rakpd.pagerduty.com" #YOUR_SUBDOMAIN e.g., yourcompany.pagerduty.com

HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Token token={PAGERDUTY_API_KEY}",
    "Content-Type": "application/json",
    "From": "ts-romuluscalu.nalus@rakuten.com" # PagerDuty recommends setting a 'From' header
}

BASE_URL = f"https://api.pagerduty.com"

# --- Configuration for filtering ---
PAGERDUTY_TEAM_IDS = [] # Keep empty list if no team filter is desired
PAGERDUTY_SERVICE_IDS = ["PJ9IYQT"] # Corrected: The Service ID is a string, replace with your actual ID(s)
# --- END Configuration ---

# Define the JST timezone for output formatting
JST_TIMEZONE = pytz.timezone('Asia/Tokyo')

def get_incidents(since, until, team_ids=None, service_ids=None):
    all_incidents = []
    offset = 0
    limit = 100

    if team_ids is None:
        team_ids = []
    if service_ids is None:
        service_ids = []

    params = {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "statuses[]": ["resolved"],
        "sort_by": "created_at:asc",
        "offset": offset,
        "limit": limit,
        "include[]": ["first_trigger_log_entry", "acknowledgements", "resolutions", "assignments", "priority"] # Include more data
    }

    if team_ids:
        params["team_ids[]"] = team_ids
    if service_ids:
        params["service_ids[]"] = service_ids

    while True:
        response = requests.get(f"{BASE_URL}/incidents", headers=HEADERS, params=params)
        response.raise_for_status()

        data = response.json()
        incidents = data.get("incidents", [])
        all_incidents.extend(incidents)

        if not data.get("more"):
            break

        offset += limit
        params["offset"] = offset
    return all_incidents


def get_incident_log_entries(incident_id):
    """Fetches all log entries for a given incident."""
    all_log_entries = []
    offset = 0
    limit = 100
    while True:
        params = {
            "offset": offset,
            "limit": limit,
            "is_overview": "false"
        }
        response = requests.get(f"{BASE_URL}/incidents/{incident_id}/log_entries", headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        log_entries = data.get("log_entries", [])
        all_log_entries.extend(log_entries)

        if not data.get("more"):
            break
        offset += limit
    return all_log_entries

def parse_incident_metrics(incident, all_log_entries):
    """Parses log entries and incident object to extract various metrics."""
    metrics = {
        "Notes": [],
        "Resolved By": "N/A",
        "Auto Resolved": False,
        "Responders": set(), # Use a set to avoid duplicate responders
        "TTA (in seconds)": "N/A",
        "TTR (in seconds)": "N/A",
        "Response Effort (in seconds)": 0,
        "Escalations": 0
    }

    # Extract notes
    for entry in all_log_entries:
        if entry.get("type") == "annotate_log_entry":
            metrics["Notes"].append(entry.get("channel", {}).get("summary", ""))

    # Timestamps for calculations
    trigger_time = None
    acknowledge_time = None
    resolve_time = None

    # Get first trigger time (from the incident object directly, it's more reliable than parsing log entries)
    if incident.get("first_trigger_log_entry"):
        trigger_time_str = incident["first_trigger_log_entry"].get("created_at")
        if trigger_time_str:
            trigger_time = datetime.fromisoformat(trigger_time_str.replace('Z', '+00:00'))

    # Get acknowledge time from incident object (if available)
    if incident.get("acknowledgements"):
        # Find the earliest acknowledgement
        earliest_ack_time = None
        for ack in incident["acknowledgements"]:
            ack_time_str = ack.get("at")
            if ack_time_str:
                current_ack_time = datetime.fromisoformat(ack_time_str.replace('Z', '+00:00'))
                if earliest_ack_time is None or current_ack_time < earliest_ack_time:
                    earliest_ack_time = current_ack_time
        acknowledge_time = earliest_ack_time

    # Get resolve time from incident object (if available)
    if incident.get("resolutions"):
        # Find the latest resolution (in case of multiple)
        latest_res_time = None
        for res in incident["resolutions"]:
            res_time_str = res.get("at")
            if res_time_str:
                current_res_time = datetime.fromisoformat(res_time_str.replace('Z', '+00:00'))
                if latest_res_time is None or current_res_time > latest_res_time:
                    latest_res_time = current_res_time
        resolve_time = latest_res_time

    # Calculate TTA (Time to Acknowledge)
    if trigger_time and acknowledge_time:
        tta_seconds = (acknowledge_time - trigger_time).total_seconds()
        if tta_seconds >= 0: # Ensure acknowledgement isn't before trigger
            metrics["TTA (in seconds)"] = int(tta_seconds)

    # Calculate TTR (Time to Resolve)
    if trigger_time and resolve_time:
        ttr_seconds = (resolve_time - trigger_time).total_seconds()
        if ttr_seconds >= 0: # Ensure resolution isn't before trigger
            metrics["TTR (in seconds)"] = int(ttr_seconds)

    # Parse log entries for Resolved By, Auto Resolved, Responders, Escalations, and more accurate Response Effort
    first_assignment_time = None
    last_assignment_time = None # To help with response effort
    
    for entry in all_log_entries:
        entry_time_str = entry.get("created_at")
        if not entry_time_str:
            continue
        entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))

        # Resolved By & Auto Resolved
        if entry.get("type") == "resolve_log_entry":
            agent = entry.get("agent", {})
            if agent.get("type") == "user_reference":
                metrics["Resolved By"] = agent.get("summary", "N/A")
                metrics["Auto Resolved"] = False
            elif agent.get("type") == "integration_reference":
                metrics["Resolved By"] = agent.get("summary", "Integration")
                metrics["Auto Resolved"] = True

        # Responders
        if entry.get("type") in ["acknowledge_log_entry", "assign_log_entry"]:
            agent = entry.get("agent", {})
            if agent.get("type") == "user_reference":
                metrics["Responders"].add(agent.get("summary", "Unknown User"))
        
        # Escalations
        if entry.get("type") == "escalate_log_entry":
            metrics["Escalations"] += 1

        # Response Effort - this is a complex metric, this is an approximation
        # We'll sum up the duration of assignments.
        # This assumes a responder is "working" on it while assigned.
        # For more accurate "response effort", PagerDuty's Analytics API is best.
        if entry.get("type") == "assign_log_entry":
            if first_assignment_time is None:
                first_assignment_time = entry_time
            last_assignment_time = entry_time # Update with each assignment

    # Finalize Response Effort (simple approximation)
    # If the incident was resolved, and we have assignment times, assume effort from first assign to resolution
    if first_assignment_time and resolve_time:
        effort_seconds = (resolve_time - first_assignment_time).total_seconds()
        if effort_seconds >= 0:
            metrics["Response Effort (in seconds)"] = int(effort_seconds)
    # If not resolved but was assigned, and we have an acknowledge time
    elif first_assignment_time and acknowledge_time and incident.get("status") != "resolved":
         effort_seconds = (acknowledge_time - first_assignment_time).total_seconds()
         if effort_seconds >= 0:
            metrics["Response Effort (in seconds)"] = int(effort_seconds)


    metrics["Notes"] = "\n--- NOTE ---\n".join(metrics["Notes"])
    metrics["Responders"] = ", ".join(sorted(list(metrics["Responders"]))) # Sort and join unique responders

    return metrics


def main():
    # --- Reporting period for November 2025 (UTC) ---
    since = datetime(2025, 11, 1, 0, 0, 0, tzinfo=timezone.utc)
    until = datetime(2025, 12, 1, 0, 0, 0, tzinfo=timezone.utc)

    print(f"Reporting period (UTC): {since} to {until}")

    incidents = get_incidents(
        since,
        until,
        team_ids=PAGERDUTY_TEAM_IDS,
        service_ids=PAGERDUTY_SERVICE_IDS
    )

    print(f"Found {len(incidents)} incidents.")

    output_data = []
    # Updated CSV Headers with new order and columns
    csv_headers = [
        "Notes",
        "Incident Number",
        "Incident Type",
        "Title",
        "Urgency",
        "Priority",
        "Service",
        "Created At (JST)",
        "Resolved By",
        "Auto Resolved",
        "Responders",
        "TTA (in seconds)",
        "TTR (in seconds)",
        "Response Effort (in seconds)",
        "Escalations"
    ]

    for incident in incidents:
        incident_id = incident.get("id")
        incident_number = incident.get("incident_number")

        # Fetch all log entries for the incident
        all_log_entries = get_incident_log_entries(incident_id)
        incident_metrics = parse_incident_metrics(incident, all_log_entries)

        # Convert created_at to JST
        created_at_utc_str = incident.get("created_at")
        created_at_jst = "N/A"
        if created_at_utc_str:
            created_at_utc = datetime.fromisoformat(created_at_utc_str.replace('Z', '+00:00'))
            created_at_jst = created_at_utc.astimezone(JST_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S %Z')

        # --- FIX APPLIED HERE for 'priority' ---
        # Get the priority object, defaulting to an empty dict if 'priority' key is missing or None
        priority_object = incident.get("priority")
        if priority_object is None:
            priority_object = {}
        priority_name = priority_object.get("summary", "N/A")
        # --- END FIX ---


        output_data.append({
            "Notes": incident_metrics["Notes"],
            "Incident Number": incident_number,
            "Incident Type": incident.get("type", "unknown"), # Incident type from the incident object
            "Title": incident.get("title"),
            "Urgency": incident.get("urgency"),
            "Priority": priority_name,
            "Service": incident.get("service", {}).get("summary"),
            "Created At (JST)": created_at_jst,
            "Resolved By": incident_metrics["Resolved By"],
            "Auto Resolved": "Yes" if incident_metrics["Auto Resolved"] else "No",
            "Responders": incident_metrics["Responders"],
            "TTA (in seconds)": incident_metrics["TTA (in seconds)"],
            "TTR (in seconds)": incident_metrics["TTR (in seconds)"],
            "Response Effort (in seconds)": incident_metrics["Response Effort (in seconds)"],
            "Escalations": incident_metrics["Escalations"]
        })

    filename = f"pagerduty_incidents_november_2025_metrics.csv"
    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
        writer.writeheader()
        writer.writerows(output_data)
    print(f"Report saved to {filename}")

if __name__ == "__main__":
    main()
