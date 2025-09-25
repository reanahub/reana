import subprocess
import click
import signal
import sys
import os
import time

# Construct the absolute path to the reana-client directory
current_dir = os.path.dirname(os.path.abspath(__file__))
reana_client_path = os.path.abspath(os.path.join(current_dir, '..', '..', 'reana-client'))

# Add the reana-client directory to the sys.path
if reana_client_path not in sys.path:
    sys.path.insert(0, reana_client_path)

from reana_client.api.client import get_workflow_logs

# Global variable to control the loop
continue_logging = True

def signal_handler(sig, frame):
    global continue_logging
    continue_logging = False
    print("Stopping log collection...")

def run_command_with_retries(command, max_retries=5, delay=2):
    attempt = 0
    while attempt < max_retries:
        try:
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return process
        except Exception as e:
            print(f"An error occurred: {e}. Attempt {attempt + 1} of {max_retries}")
            attempt += 1
            time.sleep(delay)
    print("All attempts to run the command have failed.")
    return None

@click.command()
@click.option('--log-file', required=True, help='The name of the file to save the logs.')
@click.option('--workflow', required=True, help='The name of the workflow')
def run_command_and_save_logs(log_file, workflow):
    """This script allows to check the workflow pods status and save the logs file for further graphical evaluation
        To run this script:

         Steps to run benchmarking workflow lifetime test:
        .. code-block:: console
        \b
        #To run this script 
        $ cd reana/scripts
        $ python log-kubectl.py --log-file logs-file --workflow your-workflow
    
    """
    global continue_logging

    # Get the access token from environment variable
    access_token = os.getenv('REANA_ACCESS_TOKEN')
    if not access_token:
        print("Error: REANA_ACCESS_TOKEN environment variable is not set.")
        sys.exit(1)

    # Call get_workflow_logs with the workflow and access_token
    service = get_workflow_logs(workflow, access_token)
    # Extract batch_id from the service response
    batch_id = service.get('workflow_id')
    if not batch_id:
        print("Error: 'workflow_id' not found in the service response.")
        sys.exit(1)
    print("The batch_id is suppose to be this:", batch_id)

    # Register the signal handler
    signal.signal(signal.SIGINT, signal_handler)

    command = (
        "kubectl get pod -o='custom-columns=NAME:.metadata.name,PHASE:.status.phase,"
        "CREATED:.metadata.creationTimestamp,STARTED:.status.startTime,"
        "STARTED_CONTAINERS:.status.containerStatuses[*].state.*.startedAt,"
        "FINISHED_CONTAINERS:.status.containerStatuses[*].state.*.finishedAt' -w"
    )

    with open(log_file, "a") as file:  # 'a' is for appending to the file without truncating it
        while continue_logging:
            process = run_command_with_retries(command)
            if not process:
                print("Failed to start the command")
                break
            try:
                while continue_logging:
                    line = process.stdout.readline()
                    if not line:
                        break
                    line = line.strip()  # Strip the line of leading/trailing whitespace
                    print(line)
                    file.write(line + "\n")
                    if f"reana-run-batch-{batch_id}" in line and "Failed" in line:
                        file.write(line + '\n')  # Ensure newline is added when writing to file
                        continue_logging = False
                        break
            except Exception as e:
                print(f"An error occurred while reading the process output: {e}")
            finally:
                process.terminate()
                process.wait()

if __name__ == "__main__":
    run_command_and_save_logs()
