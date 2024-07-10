import pandas as pd
import subprocess
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter, SecondLocator
import click

"""Run this script to generate the plots of current job status"""
"""First compare the logs from reana-client logs command and the job pod ID's from statistics file"""

def run_reana_client_logs(command):
    command = f"reana-client logs -w {workflow}"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout
    else:
        print("Comamnd failed to run, error:")
        print(result.stderr)
        return None

def parse_log_file(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()
    return lines

def extract_unique_jobs(lines):
    unique_jobs = {}
    for line in lines:
        if line.strip().startswith('reana-run-job-'):
            job_id = line.strip().split()[0]
            unique_jobs[job_id] = line.strip()
    return unique_jobs.values()

def extract_succeeded_timestamps(unique_jobs):
    succeeded_timestamps = [line.split()[5] for line in unique_jobs if line.split()[5] != "<none>"]
    succeeded_timestamps = [ts.split(',')[0] for ts in succeeded_timestamps]
    return pd.to_datetime(succeeded_timestamps, errors='coerce')

def get_sorted_data(lines):
    sorted_data = sorted(lines, key=lambda x: x.split()[1])
    return sorted_data

def filter_jobs(sorted_data, status):
    return [line for line in sorted_data if line.split()[1] == status]

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

def calculate_cumulative(timestamps):
    x = []
    y = []
    cumulative_sum = 0
    for timestamp in timestamps:
        cumulative_sum += timestamp[1]
        x.append(timestamp[0])
        y.append(cumulative_sum)
    return x, y
 
def plot_data(succeeded_counts, x_running, y_running, x_pending, y_pending):
    plt.figure(figsize=figsize)

    # Plot succeeded jobs
    plt.plot(succeeded_counts.index, succeeded_counts.cumsum(), label='Finished', linestyle='-', color='green', alpha=0.5)

    # Plot running jobs
    plt.plot(x_running, y_running, linestyle='-', color='blue', alpha=0.5, linewidth=3, label='Running')

    # Plot pending jobs
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
@click.option('--workflow', required=False, help='Name of the REANA workflow the same as the processed .txt file')
def main(file_path, title, figsize, workflow):
    """Compare the reana-client logs and the jobs from the analysis results
       Run benchmarking tests. Generate matplotlib plot

       The script requires matplotlib and pandas packages

       Steps to run benchmarking workflow lifetime test:

        .. code-block:: console

        \b
        #To run this script 
        $ kubectl #To save a live logs 
        $ cd reana/scripts
        $ python lifetime.py logs.txt # insert your .txt file with logs

    """
    reana_logs = run_reana_client_logs(workflow)
    reana_job_ids = set()
    for line in reana_logs.splitlines():
        if line.strip().startswith('reana-run-job'):
            job_id  = line.strip().split()[0]
            reana_job_ids.add(job_id)
    lines = parse_log_file(file_path)
    
    unique_jobs = extract_unique_jobs(lines)
    succeeded_timestamps = extract_succeeded_timestamps(unique_jobs)
    first_succeeded_timestamp = succeeded_timestamps.dropna().min()
    succeeded_counts = succeeded_timestamps.value_counts().sort_index()
    
    sorted_data = get_sorted_data(lines)
    
    running_jobs = filter_jobs(sorted_data, 'Running')
    timestamps_running = extract_running_timestamps(running_jobs)
    x_running, y_running = calculate_cumulative(timestamps_running)
    
    pending_jobs = filter_jobs(sorted_data, 'Pending')
    timestamps_pending = extract_pending_timestamps(pending_jobs)
    x_pending, y_pending = calculate_cumulative(timestamps_pending)
    
    plot_data(succeeded_counts, x_running, y_running, x_pending, y_pending)

if __name__ == "__main__":
    main()
