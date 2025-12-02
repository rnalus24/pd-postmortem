
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
                sh '. venv/bin/activate && pip install requests pytz'
                echo "Python environment prepared."
            }
        }
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
                // This will archive any file ending with .csv in your workspace
                archiveArtifacts artifacts: '*.csv', fingerprint: true
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

