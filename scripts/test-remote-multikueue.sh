#!/bin/bash

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to echo commands before running them
run_cmd() {
    echo -e "${BLUE}+ $*${NC}" >&2
    "$@"
}

# Function to print colored messages
print_msg() {
    local color=$1
    shift
    echo -e "${color}$*${NC}"
}

print_error() {
    print_msg "$RED" "ERROR: $*" >&2
}

print_status() {
    print_msg "$GREEN" "✓ $*"
}

print_info() {
    print_msg "$YELLOW" "→ $*"
}

print_section() {
    echo
    print_msg "$CYAN" "=================================================================================="
    print_msg "$CYAN" "$*"
    print_msg "$CYAN" "=================================================================================="
    echo
}

# Cleanup function
# shellcheck disable=SC2317 # Not unreachable - called by trap
cleanup() {
    local exit_code=$?
    if [ "$exit_code" -ne 0 ]; then
        print_error "Test failed. Check the error messages above."
    fi
}

trap cleanup EXIT

# Handle --remote flag passed
while [[ $# -gt 0 ]]; do
    case $1 in
    --remote)
        if [[ -z "$2" ]]; then
            print_error "--remote requires a value"
            exit 1
        fi
        REMOTE="$2"
        REMOTE_KUBECONFIG="$2.kubeconfig"
        shift
        ;;
    *)
        print_error "Unknown option: $1"
        exit 1
        ;;
    esac
    shift
done

print_section "Testing Remote MultiKueue Setup"

# Clean up any existing test jobs
print_info "Cleaning up any existing test jobs..."
kubectl delete jobs --all 2>/dev/null || true
kubectl --kubeconfig="$REMOTE_KUBECONFIG" delete jobs --all 2>/dev/null || true

print_section "Step 1: Submit Job to Remote Queue"

# Create test job for remote queue using sample-job.yaml template
print_info "Creating remote test job from sample-job.yaml template..."
sed 's/site: somewhere/site: '"$REMOTE"'/g' "$(dirname "$0")/../etc/sample-job.yaml" >remote-test-job.yaml

print_info "Submitting job to remote queue..."
run_cmd kubectl apply -f remote-test-job.yaml

print_section "Step 2: Monitor Job Dispatch to Remote Cluster"

print_info "Waiting for job to be dispatched to remote cluster..."
TIMEOUT=20
COUNTER=0

while [ $COUNTER -lt $TIMEOUT ]; do
    # Check if job exists on remote cluster
    if kubectl --kubeconfig="$REMOTE_KUBECONFIG" get job remote-test-job 2>/dev/null | grep -q "remote-test-job"; then
        print_status "Job successfully dispatched to remote cluster!"
        break
    fi

    echo -n "."
    sleep 1
    COUNTER=$((COUNTER + 1))
done

if [ $COUNTER -eq $TIMEOUT ]; then
    print_error "Timeout waiting for job dispatch to remote cluster"

    # Debug information
    print_info "Manager cluster job status:"
    kubectl get jobs

    print_info "Manager cluster workloads:"
    kubectl get workloads

    print_info "MultiKueue controller logs:"
    kubectl logs -n kueue-system deployment/kueue-controller-manager --tail=50

    exit 1
fi

print_section "Step 3: Monitor Job Execution on Remote Cluster"

print_info "Job status on MANAGER cluster:"
run_cmd kubectl get jobs -o wide

print_info "Job status on REMOTE cluster:"
run_cmd kubectl --kubeconfig="$REMOTE_KUBECONFIG" get jobs -o wide

print_info "Waiting for job to start on remote cluster..."
run_cmd kubectl --kubeconfig="$REMOTE_KUBECONFIG" wait --for=condition=ready pod -l job-name=remote-test-job --timeout=60s || true

# Get pod name on remote cluster - try multiple approaches
REMOTE_POD=""

# First, try to find pod using job-name label (works when job exists)
REMOTE_POD=$(kubectl --kubeconfig="$REMOTE_KUBECONFIG" get pods -l job-name=remote-test-job -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

# If no pod found with job-name label, try to find the newest busybox pod
if [ -z "$REMOTE_POD" ]; then
    print_info "Job-based pod lookup failed, searching for recent busybox pods on remote cluster..."
    REMOTE_POD=$(kubectl --kubeconfig="$REMOTE_KUBECONFIG" get pods --sort-by=.metadata.creationTimestamp -o jsonpath='{range .items[*]}{.metadata.creationTimestamp}{" "}{.metadata.name}{" "}{.spec.containers[0].image}{"\n"}{end}' 2>/dev/null | grep "busybox" | tail -1 | awk '{print $2}' || echo "")

    if [ -z "$REMOTE_POD" ]; then
        print_info "No busybox pod found, getting most recent pod on remote cluster..."
        REMOTE_POD=$(kubectl --kubeconfig="$REMOTE_KUBECONFIG" get pods --sort-by=.metadata.creationTimestamp --no-headers -o custom-columns=":metadata.name" 2>/dev/null | tail -1 || echo "")
    fi
fi

if [ -n "$REMOTE_POD" ]; then
    print_info "Found remote pod: $REMOTE_POD"

    # Check if pod is already completed
    POD_STATUS=$(kubectl --kubeconfig="$REMOTE_KUBECONFIG" get pod "$REMOTE_POD" -o jsonpath='{.status.phase}' 2>/dev/null || echo "")

    print_msg "$MAGENTA" "--- Remote Job Logs ---"
    if [ "$POD_STATUS" = "Succeeded" ] || [ "$POD_STATUS" = "Failed" ]; then
        print_info "Pod already completed with status: $POD_STATUS. Getting complete logs:"
        run_cmd kubectl --kubeconfig="$REMOTE_KUBECONFIG" logs "$REMOTE_POD" || echo "No logs available"
    else
        print_info "Pod is running, streaming logs from remote cluster pod: $REMOTE_POD"
        run_cmd kubectl --kubeconfig="$REMOTE_KUBECONFIG" logs "$REMOTE_POD" -f --tail=100 || true
    fi
    print_msg "$MAGENTA" "--- End of Remote Job Logs ---"
    echo
fi

print_section "Step 4: Verify Job Completion"

print_info "Checking for job completion on remote cluster..."
JOB_COMPLETED=false
if kubectl --kubeconfig="$REMOTE_KUBECONFIG" get job remote-test-job >/dev/null 2>&1; then
    if run_cmd kubectl --kubeconfig="$REMOTE_KUBECONFIG" wait --for=condition=complete job/remote-test-job --timeout=120s; then
        print_status "Job completed successfully on remote cluster!"
        JOB_COMPLETED=true
    else
        print_error "Job did not complete within timeout"
        JOB_COMPLETED=false
    fi
else
    print_info "Job not found (may have been cleaned up already). Checking pod status instead..."
    if [ -n "$REMOTE_POD" ]; then
        POD_STATUS=$(kubectl --kubeconfig="$REMOTE_KUBECONFIG" get pod "$REMOTE_POD" -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
        print_info "Pod status: $POD_STATUS"
        if [ "$POD_STATUS" = "Succeeded" ]; then
            print_status "Job completed successfully (determined from pod status)!"
            JOB_COMPLETED=true
        else
            print_error "Job did not complete successfully (pod status: $POD_STATUS)"
            JOB_COMPLETED=false
        fi
    else
        print_error "No job or pod found to determine completion status"
        JOB_COMPLETED=false
    fi
fi

print_section "Step 5: Final Status Check"

print_info "Final job status on MANAGER cluster:"
run_cmd kubectl get jobs -o wide

print_info "Final job status on REMOTE cluster:"
run_cmd kubectl --kubeconfig="$REMOTE_KUBECONFIG" get jobs -o wide

print_info "Workload status on manager cluster:"
run_cmd kubectl get workloads -o wide

print_info "Remote cluster events:"
run_cmd kubectl --kubeconfig="$REMOTE_KUBECONFIG" get events --sort-by='.lastTimestamp' | tail -10

print_section "Test Results"

# Check if job completed successfully (using the kubectl wait result)
if [ "$JOB_COMPLETED" = "true" ]; then
    echo ""
    echo -e "${GREEN}🎉 Remote cluster MultiKueue test complete!${NC}"
    echo ""
    echo "Summary:"
    echo "- Job submitted to manager cluster ✅"
    echo "- Job dispatched to remote cluster ✅"
    echo "- Job executed on remote cluster ✅"
    echo ""
    echo "Your MultiKueue setup is working correctly! 🚀"

    # Clean up test resources
    print_info "Cleaning up test resources..."
    kubectl delete -f remote-test-job.yaml >/dev/null 2>&1 || true                      # Remove from manager cluster (job manifest)
    kubectl --kubeconfig="$REMOTE_KUBECONFIG" delete jobs --all >/dev/null 2>&1 || true # Remove from remote cluster
    rm -f remote-test-job.yaml

    exit 0
else
    print_error "Remote MultiKueue test FAILED"
    print_info "Check the logs above for troubleshooting information"
    print_info "Job did not complete within the timeout period"
    exit 1
fi
