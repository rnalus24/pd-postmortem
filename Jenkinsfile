```groovy
// Jenkinsfile
pipeline {
    agent any // Or a specific agent label if you have one, e.g., agent { label 'python-agent' }

    environment {
        // Retrieve the API Key from Jenkins Credentials
        PAGERDUTY_API_KEY = credentials('PAGERDUTY_API_KEY')
        PAGERDUTY_SUBDOMAIN = "rakpd.pagerduty.com" // e.g., "mycompany"
        OUTPUT_FILE = "pagerduty_incidents_with_notes.csv"
        PYTHON_SCRIPT_FILE = "pagerduty_metrics_extractor.py"
    }

    stages {
        stage('Prepare Python Environment') {
            steps {
                // Ensure Python and pip are available
                sh 'which python3'
                sh 'which pip3'

                // Create a virtual environment
                sh 'python3 -m venv venv'
                // Activate the virtual environment and install dependencies
                // Use 'pip' from the venv directly, not 'pip3' from system
                sh '. venv/bin/activate && pip install requests'
                echo "Python environment prepared."
            }
        }
"""
        stage('Create Python Script') {
            steps {
                // Write the Python script content directly into a file in the workspace.
                // Alternatively, if the script is part of your SCM, you can skip this step.
                writeFile file: "${PYTHON_SCRIPT_FILE}", text: '''
import requests
import json
import csv
import os
from datetime import datetime, timedelta

# Configuration from environment variables
PAGERDUTY_API_KEY = os.getenv("PAGERDUTY_API_KEY")
PAGERDUTY_SUBDOMAIN = os.getenv("PAGERDUTY_SUBDOMAIN")
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "pagerduty_incidents_with_notes.csv")

if not PAGERDUTY_API_KEY or not PAGERDUTY_SUBDOMAIN:
    print("Error: PAGERDUTY_API_KEY or PAGERDUTY_SUBDOMAIN not set.")
    exit(1)

HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Token token={PAGERDUTY_API_KEY}",
    "Content-Type": "application/json",
    "From": "jenkins@yourcompany.com" # PagerDuty recommends setting a 'From' header
}

BASE_URL = f"https://api.pagerduty.com"

def get_incidents(since, until):
    all_incidents = []
    offset = 0
    limit = 100

    while True:
        params = {
            "since": since.isoformat(),
            "until": until.isoformat(),
            "statuses[]": ["triggered", "acknowledged", "resolved"],
            "sort_by": "created_at:asc",
            "offset": offset,
            "limit": limit
        }
        response = requests.get(f"{BASE_URL}/incidents", headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        incidents = data.get("incidents", [])
        all_incidents.extend(incidents)

        if not data.get("more"):
            break
        offset += limit
    return all_incidents

def get_incident_notes(incident_id):
    notes = []
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

        for entry in log_entries:
            if entry.get("type") == "annotate_log_entry":
                notes.append(entry.get("channel", {}).get("content", ""))
        if not data.get("more"):
            break
        offset += limit
    return "\n--- NOTE ---\n".join(notes)

def main():
    until = datetime.utcnow()
    since = until - timedelta(days=7) # Last 7 days

    incidents = get_incidents(since, until)
    print(f"Found {len(incidents)} incidents.")

    output_data = []
    csv_headers = [
        "Incident ID", "Title", "Service", "Status", "Created At",
        "Resolved At", "Assigned To", "Urgency", "Notes"
    ]

    for incident in incidents:
        incident_id = incident.get("id")
        incident_notes = get_incident_notes(incident_id)

        assigned_to = ", ".join([assignee.get("summary", "") for assignee in incident.get("assignments", [])])

        output_data.append({
            "Incident ID": incident_id,
            "Title": incident.get("title"),
            "Service": incident.get("service", {}).get("summary"),
            "Status": incident.get("status"),
            "Created At": incident.get("created_at"),
            "Resolved At": incident.get("resolved_at"),
            "Assigned To": assigned_to,
            "Urgency": incident.get("urgency"),
            "Notes": incident_notes
        })

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
        writer.writeheader()
        writer.writerows(output_data)
    print(f"Report saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
'''
                echo "Python script created: ${PYTHON_SCRIPT_FILE}"
            }
        }
"""
        stage('Run Python Script') {
            steps {
                // Activate venv and run the script, passing environment variables
                sh """
                    . venv/bin/activate && \\
                    PAGERDUTY_API_KEY="${PAGERDUTY_API_KEY}" \\
                    PAGERDUTY_SUBDOMAIN="${PAGERDUTY_SUBDOMAIN}" \\
                    OUTPUT_FILE="${OUTPUT_FILE}" \\
                    python3 "${PYTHON_SCRIPT_FILE}"
                """
                echo "Python script executed."
            }
        }

        stage('Archive Report') {
            steps {
                archiveArtifacts artifacts: "${OUTPUT_FILE}", fingerprint: true
            }
        }

        stage('Cleanup Environment') {
            steps {
                // Optional: Remove the virtual environment
                sh 'rm -rf venv'
                echo "Cleaned up virtual environment."
            }
        }
    }

    post {
        always {
            // Clean up the generated script file
            sh "rm -f ${PYTHON_SCRIPT_FILE}"
        }
        failure {
            echo 'Pipeline failed. Check logs for details.'
        }
    }
}
```