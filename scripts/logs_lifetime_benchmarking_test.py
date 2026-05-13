import subprocess
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter, SecondLocator
import click
import os
import re
import sys
import logging
from reana_client.api.client import get_workflow_logs

# Ensure REANA_ACCESS_TOKEN is set
access_token = os.getenv('REANA_ACCESS_TOKEN')
if not access_token:
    print("Error: REANA_ACCESS_TOKEN environment variable is not set.")
    sys.exit(1)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Function to extract job IDs from lines
def extract_job_ids_from_lines(lines):
    job_ids = set()
    for line in lines:
        match = re.search(r'reana-run-job-\w{8}-\w{4}-\w{4}-\w{4}-\w{12}', line)
        if match:
            job_ids.add(match.group(0))
    return job_ids

# Function to parse log file
def parse_log_file(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()
    return lines

# Function to write filtered lines to a new file
def write_filtered_log_file(filtered_lines, filtered_file_path):
    with open(filtered_file_path, 'w') as f:
        f.writelines(filtered_lines)

# Function to extract unique jobs from lines
def extract_unique_jobs(lines):
    unique_jobs = {}
    for line in lines:
        match = re.match(r'(reana-run-job-\w{8}-\w{4}-\w{4}-\w{4}-\w{12})', line)
        if match:
            job_id = match.group(0)
            unique_jobs[job_id] = line.strip()
    return unique_jobs.values()

# Function to extract succeeded timestamps from unique jobs
def extract_succeeded_timestamps(unique_jobs):
    succeeded_timestamps = [line.split()[5] for line in unique_jobs if line.split()[5] != "<none>"]
    succeeded_timestamps = [ts.split(',')[0] for ts in succeeded_timestamps]
    return pd.to_datetime(succeeded_timestamps, errors='coerce')

# Function to get sorted data by timestamp
def get_sorted_data(lines):
    sorted_lines = []
    for line in lines:
        parts = line.split()
        try:
            timestamp = pd.to_datetime(parts[2])
            sorted_lines.append((timestamp, line))
        except Exception as e:
            logger.error(f"Error parsing date from line: {line}. Error: {e}")
    sorted_lines.sort(key=lambda x: x[0])
    return [line for _, line in sorted_lines]

# Function to filter jobs based on status
def filter_jobs(sorted_data, status):
    return [line for line in sorted_data if line.split()[1] == status]

# Function to extract running timestamps
def extract_running_timestamps(running_jobs):
    timestamps_running = []
    encountered_jobs_running = set()

    for line in running_jobs:
        parts = line.split()
        job_id = parts[0]
        if job_id in encountered_jobs_running:
            continue

        start_time = pd.to_datetime(parts[3])
        finish_time_str = parts[5].split(',')[0]

        if finish_time_str != '<none>':
            finish_time = pd.to_datetime(finish_time_str)
            timestamps_running.append((start_time, 1))
            timestamps_running.append((finish_time, -1))
            encountered_jobs_running.add(job_id)

    timestamps_running.sort()
    return timestamps_running

# Function to extract pending timestamps
def extract_pending_timestamps(pending_jobs):
    timestamps_pending = []
    encountered_jobs_pending = set()

    for line in pending_jobs:
        parts = line.split()
        job_id = parts[0]
        if job_id in encountered_jobs_pending:
            continue

        start_time_str = parts[2]
        if start_time_str == '<none>':
            continue

        start_time = pd.to_datetime(start_time_str)
        finish_time_str = parts[3].split(',')[0]

        if finish_time_str != '<none>':
            finish_time = pd.to_datetime(finish_time_str)
            timestamps_pending.append((start_time, 1))
            timestamps_pending.append((finish_time, -1))
            encountered_jobs_pending.add(job_id)

    timestamps_pending.sort()
    return timestamps_pending

# Function to calculate cumulative timestamps
def calculate_cumulative(timestamps):
    x = []
    y = []
    cumulative_sum = 0
    for timestamp in timestamps:
        cumulative_sum += timestamp[1]
        x.append(timestamp[0])
        y.append(cumulative_sum)
    return x, y

# Function to plot data
def plot_data(succeeded_counts, x_running, y_running, x_pending, y_pending, title, figsize):
    plt.figure(figsize=figsize)
    plt.plot(succeeded_counts.index, succeeded_counts.cumsum(), label='Finished', linestyle='-', color='green', alpha=0.5)
    plt.plot(x_running, y_running, linestyle='-', color='blue', alpha=0.5, linewidth=3, label='Running')
    plt.plot(x_pending, y_pending, linestyle='-', color='orange', alpha=0.5, linewidth=3, label='Pending')
    plt.xlabel('Processing time')
    plt.ylabel('Number of Jobs')
    plt.title(title)
    plt.gca().xaxis.set_major_formatter(DateFormatter("%H:%M:%S"))
    plt.gca().xaxis.set_major_locator(SecondLocator(interval=40))
    plt.grid(True)
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

@click.command()
@click.argument('file_path')
@click.option('--title', default='Analysis Results', help='Title of the analysis results')
@click.option('--figsize', nargs=2, type=float, default=(12, 8), help='Figure size as two float values')
@click.option('--workflow', required=True, help='Name of the REANA workflow')
def main(file_path, title, figsize, workflow):
    """ This script allows to plot the workflow lifetime statistics.
     As a results of evaluating the logs file with pod life cycle information,
     the statistics of how many jobe were running in parallel can be found.


     Steps to run benchmarking workflow lifetime test:
        .. code-block:: console
        \b
        #To run this script 
        $ kubectl #To save a live logs 
        $ cd reana/scripts
        $ python lifetime.py logs.txt # insert your .txt file with logs  and the name of the workflow
    """
    service = get_workflow_logs(workflow, access_token)
    log_string = service['logs']
    reana_run_job_ids = re.findall(r'reana-run-job-\w{8}-\w{4}-\w{4}-\w{4}-\w{12}', log_string)
    
    lines = parse_log_file(file_path)
    file_job_ids = extract_job_ids_from_lines(lines)
    
    diff_job_ids = set(reana_run_job_ids).symmetric_difference(file_job_ids)
    if diff_job_ids:
        print("Differing Job IDs:")
        for job_id in diff_job_ids:
            print(job_id)
    else:
        print("No differing Job IDs found.")
    
    filtered_lines = [line for line in lines if not any(job_id in line for job_id in diff_job_ids)]
    filtered_file_path = 'filtered_' + file_path
    write_filtered_log_file(filtered_lines, filtered_file_path)
    
    unique_jobs = extract_unique_jobs(filtered_lines)
    succeeded_timestamps = extract_succeeded_timestamps(unique_jobs)
    succeeded_counts = succeeded_timestamps.value_counts().sort_index()
    
    sorted_data = get_sorted_data(filtered_lines)
    running_jobs = filter_jobs(sorted_data, 'Running')
    timestamps_running = extract_running_timestamps(running_jobs)
    x_running, y_running = calculate_cumulative(timestamps_running)
    
    pending_jobs = filter_jobs(sorted_data, 'Pending')
    timestamps_pending = extract_pending_timestamps(pending_jobs)
    x_pending, y_pending = calculate_cumulative(timestamps_pending)
    
    plot_data(succeeded_counts, x_running, y_running, x_pending, y_pending, title, figsize)

if __name__ == "__main__":
    main()
