// Jenkinsfile

pipeline {
    agent any // Or a specific agent label if you have one, e.g., agent { label 'python-agent' }

    // Define general environment variables here if they are NOT sensitive
    environment {
        // PAGERDUTY_SUBDOMAIN is hardcoded in Python script; if you want to pass it:
        // PAGERDUTY_SUBDOMAIN = "rakpd.pagerduty.com"
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
                sh '. venv/bin/activate && pip install requests pytz'
                echo "Python environment prepared."
            }
        }

        stage('Generate PagerDuty Report') {
            steps {
                // Securely retrieve the PagerDuty API Key from Jenkins Credentials
                // and pass it as a command-line argument to the Python script.
                withCredentials([string(credentialsId: 'PAGERDUTY_API_KEY', variable: 'PD_API_KEY_SECRET')]) {
                    // --- OPTION 1 IMPLEMENTATION ---
                    // Using a single-quoted string to prevent Groovy String interpolation
                    // The secret is passed as a shell variable to the python script
                    sh 'export PAGERDUTY_API_KEY_ARG="$PD_API_KEY_SECRET" && . venv/bin/activate && python3 "${PYTHON_SCRIPT_FILE}" "$PAGERDUTY_API_KEY_ARG"'
                    // --- END OPTION 1 IMPLEMENTATION ---
                }
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

    // Post-build actions (always, failure, success, etc.)
    post {
        always {
            // This runs regardless of build outcome
            deleteDir() // Clean up the entire workspace
            echo 'Workspace cleaned up.'
        }
        failure {
            echo 'Pipeline failed. Check logs for details.'
        }
        success {
            echo 'Pipeline completed successfully.'
        }
    }
}
