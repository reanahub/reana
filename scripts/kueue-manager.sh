#!/bin/bash

# Kueue Management Script
# Install, configure, or remove a single Kueue cluster

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

CLUSTER_MODE="local"
REMOTE_KUBECONFIG=""
HELPER_POD="reana-run-transfer"
MULTIKUEUE_CONFIG="multikueue-config"

find_kubeconfigs() {
    local kubeconfigs
    kubeconfigs=$(find "$PWD" -maxdepth 1 -name '*-kubeconfig.yaml' 2>/dev/null |
        sed 's/-kubeconfig\.yaml$//' |
        xargs -n1 basename |
        paste -sd ',' -)
    echo "$kubeconfigs"
}

find_resources_files() {
    local resources_files
    resources_files=$(find "$PWD" -maxdepth 1 -name '*-resources.yaml' 2>/dev/null)
    echo "$resources_files"
}

# Check the current directory for any *-kubeconfig.yaml files and build a list of names (without the file extension)
REMOTES=$(find_kubeconfigs)

# Default config for monitor command
MONITOR_REFRESH_INTERVAL_SECS=3

# Default config for remove command
REMOVE_ALL=false
REMOVE_WORKLOADS=false
REMOVE_RESOURCES=false
REMOVE_KUEUE=false

#############################################################################
# Display Functions
#############################################################################

print_status() {
    if [ "$CLUSTER_MODE" = "remote" ]; then
        echo -e "| ${GREEN}✅ $1${NC}"
    else
        echo -e "${GREEN}✅ $1${NC}"
    fi
}

print_warning() {
    if [ "$CLUSTER_MODE" = "remote" ]; then
        echo -e "| ${YELLOW}⚠️  $1${NC}"
    else
        echo -e "${YELLOW}⚠️  $1${NC}"
    fi
}

print_info() {
    if [ "$CLUSTER_MODE" = "remote" ]; then
        echo -e "| ${BLUE}ℹ️  $1${NC}"
    else
        echo -e "${BLUE}ℹ️  $1${NC}"
    fi
}

print_error() {
    if [ "$CLUSTER_MODE" = "remote" ]; then
        echo -e "| ${RED}❌ $1${NC}"
    else
        echo -e "${RED}❌ $1${NC}"
    fi
}

print_section() {
    if [ "$CLUSTER_MODE" = "remote" ]; then
        echo -e "| ${BLUE}$1${NC}"
    else
        echo -e "${BLUE}$1${NC}"
    fi
}

print_command() {
    if [ "$CLUSTER_MODE" = "remote" ]; then
        echo -e "| ${YELLOW}$ $*${NC}"
    else
        echo -e "${YELLOW}$ $*${NC}"
    fi
}

#############################################################################
# Command Execution Functions
#############################################################################

kubectl_cmd() {
    if [ "$CLUSTER_MODE" = "remote" ]; then
        kubectl --kubeconfig="$REMOTE_KUBECONFIG" "$@"
    else
        kubectl "$@"
    fi
}

kubectl_with() {
    local mode="$1"
    shift # Remove mode from arguments

    if [ "$mode" = "local" ]; then
        kubectl "$@"
    else
        kubectl --kubeconfig="$mode-kubeconfig.yaml" "$@"
    fi
}

helm_cmd() {
    if [ "$CLUSTER_MODE" = "remote" ]; then
        helm --kubeconfig="$REMOTE_KUBECONFIG" "$@"
    else
        helm "$@"
    fi
}

run_cmd() {
    print_command "$@"
    "$@"
}

#############################################################################

kueue_namespace_exists() {
    kubectl_cmd get namespace kueue-system &>/dev/null
}

# Check if Kueue is installed
check_kueue_installed() {
    local mode="$1" # "quiet" or ""

    if helm_cmd list -n kueue-system | grep -q kueue; then
        local version
        version=$(helm_cmd list -n kueue-system -o json | jq -r '.[] | select(.name=="kueue") | .app_version' 2>/dev/null || echo "unknown")
        if [ "$mode" != "quiet" ]; then
            print_status "Kueue is installed. Helm release found (version: $version)"
        fi
        return 0
    else
        if [ "$mode" != "quiet" ]; then
            if kueue_namespace_exists; then
                print_warning "Kueue namespace exists but Helm release not found (maybe Kueue was installed via kubectl?)"
            else
                print_warning "Kueue is not installed."
            fi
        fi
        return 1
    fi
}

get_secret_name() {
    local node="$1"
    echo "$node-secret"
}

get_multikueue_cluster_name() {
    local node="$1"
    echo "$node-multikueue-cluster"
}

# Wait for resource cleanup with timeout
wait_for_cleanup() {
    local resource_type="$1"
    local namespace_flag="$2"
    local timeout=30
    local count=0

    print_info "Waiting for $resource_type cleanup..."
    while [ $count -lt $timeout ]; do
        if [ "$(kubectl_cmd get "$resource_type" "$namespace_flag" --no-headers 2>/dev/null | wc -l)" -eq 0 ]; then
            return 0
        fi
        sleep 1
        ((count++))
    done
    return 1
}

# Delete resources with error handling
delete_resources() {
    local resource_type="$1"

    # Delete all resources of this type
    kubectl_cmd get "$resource_type" --no-headers 2>/dev/null | while read -r resource_name rest; do
        echo "Resource name: $resource_name"

        echo -e "${BLUE}   - Deleting $resource_type $resource_name...${NC}"
        kubectl_cmd delete "$resource_type" "$resource_name" --all-namespaces --ignore-not-found=true --timeout=20s
    done
}

# Force delete resources
force_delete_resources() {
    local kind="$1" # resource kind
    local name="$2" # resource name (optional)
    local ns_flag="$3"

    print_info "Force deleting $kind $name resources..."

    if [ -n "$name" ]; then
        # Single resource delete
        kubectl_cmd patch "$kind" "$name" ${ns_flag:+$ns_flag} \
            --type merge -p '{"metadata":{"finalizers":[]}}' 2>/dev/null || true
        kubectl_cmd delete "$kind" "$name" ${ns_flag:+$ns_flag} \
            --force --grace-period=0 --ignore-not-found=true --wait=false 2>/dev/null || true
    else
        # Delete all resources of that kind
        resources=$(kubectl_cmd get "$kind" ${ns_flag:+$ns_flag} -o name 2>/dev/null || true)

        for res in $resources; do
            # Strip finalizers first
            kubectl_cmd patch "$res" --type merge -p '{"metadata":{"finalizers":[]}}' 2>/dev/null || true

            # Now delete forcefully, without waiting
            kubectl_cmd delete "$res" \
                --force --grace-period=0 --ignore-not-found=true --wait=false 2>/dev/null || true
        done
    fi
}

# Count and display resources
count_and_display_resources() {
    local resource_type="$1"
    local namespace_flag="$2" # Optional: -A for all namespaces
    local display_name="$3"

    local raw_count
    raw_count=$(kubectl_cmd get "$resource_type" ${namespace_flag:+namespace_flag} --no-headers 2>/dev/null | wc -l)

    # Trim the raw count output
    local count
    count=$(echo "$raw_count" | tr -d '[:space:]')

    if [ "$count" -gt 0 ]; then
        echo -e "${BLUE} - $display_name ($count found):${NC}"
        kubectl_cmd get "$resource_type" ${namespace_flag:+namespace_flag} --no-headers 2>/dev/null | while read -r line; do
            echo -e "${YELLOW}   • $line${NC}"
        done
        return 0 # Success - resources found
    else
        print_info "No $display_name found"
        return 1 # No resources found
    fi
}

# Comprehensive resource verification
verify_kueue_resources() {
    local mode="$1" # Optional: "require-resources" or "require-no-resources"
    local has_resources=false

    print_section "🔍 Checking Kueue resources..."

    # Check each resource type
    if count_and_display_resources "clusterqueue" "" "ClusterQueues"; then
        has_resources=true
    fi

    if count_and_display_resources "localqueue" "-A" "LocalQueues"; then
        has_resources=true
    fi

    if count_and_display_resources "resourceflavor" "" "ResourceFlavors"; then
        has_resources=true
    fi

    if count_and_display_resources "workloads" "-A" "Workloads"; then
        has_resources=true
    fi

    # Return whether resources were found
    if [ "$has_resources" = "true" ] && [ "$mode" = "require-no-resources" ]; then
        return 1 # Error: resources found
    elif [ "$has_resources" = "false" ] && [ "$mode" = "require-resources" ]; then
        return 1 # Error: no resources found
    else
        return 0 # Success
    fi
}

# Install Kueue
install_kueue() {
    # Check for existence of Kubernetes cluster
    # shellcheck disable=SC2086
    if ! kubectl_cmd get nodes | grep -q "Ready"; then
        print_error "Could not find Kubernetes cluster."
        exit 1
    fi

    if check_kueue_installed; then
        print_status "Kueue is already installed"
        return 0
    fi

    print_section "📦 Installing Kueue..."
    helm_cmd install kueue oci://registry.k8s.io/kueue/charts/kueue \
        --version=0.13.2 \
        --namespace kueue-system \
        --create-namespace \
        --wait --timeout 300s

    # Verify installation
    if check_crds_installed "check"; then
        print_status "Kueue installed successfully"
    else
        print_error "There were problems while installing Kueue. It may not be installed or some CRDs may be missing. Run '$0 status' to check. If only CRDs are missing, please run '$0 remove' and try installing again."
    fi
}

check_if_resources_already_applied() {
    # Check if any of the resources in the file already exist
    local resources_file="$1"

    local count
    count=$(yq e '.resources | length' "$resources_file")
    for ((i = 0; i < count; i++)); do
        local name
        name=$(yq e ".resources[$i].name" "$resources_file")
        if kubectl get resourceflavor "$name" >/dev/null 2>&1; then
            # If the resourceflavor has the same name and the same cpu/memory quotas, it's okay.
            local cpu memory actual_cpu actual_memory
            cpu=$(yq e ".resources[$i].cpu" "$resources_file")
            memory=$(yq e ".resources[$i].memory" "$resources_file")

            actual_cpu=$(kubectl get clusterqueue local-job-queue -o yaml |
                yq -r '.spec.resourceGroups[].flavors[]
                     | select(.name=="'"$name"'")
                     | .resources[]
                     | select(.name=="cpu")
                     | .nominalQuota')

            actual_memory=$(kubectl get clusterqueue local-job-queue -o yaml |
                yq -r '.spec.resourceGroups[].flavors[]
                     | select(.name=="'"$name"'")
                     | .resources[]
                     | select(.name=="memory")
                     | .nominalQuota')

            if [ "$cpu" = "$actual_cpu" ] && [ "$memory" = "$actual_memory" ]; then
                continue
            fi

            # Otherwise we will be overwriting the existing resourceflavor
            print_warning "ResourceFlavor $name cannot be applied because it already exists either locally or on some remote. Overwriting is a dangerous operation because it could leave ResourceFlavors in an inconsistent state. If you want to redefine ResourceFlavor $name, please delete it from your manager cluster and all remote clusters and try again."
            return 0
        fi
    done
    return 1
}

apply_resource_file() {
    # If REMOTE is not set, default to local
    local node="$1"
    local resources_file="$node-resources.yaml"

    # Build ResourceFlavor sections based on the resourceFlavors value in the remote-resources.yaml file.
    # Example remote-resources.yaml:
    # resources:
    #   - name: "default"
    #     cpu: 4
    #     memory: 8Gi
    #   - name: "highcpu"
    #     cpu: 16
    #     memory: 8Gi

    local resource_flavor_definitions=""
    local job_cluster_queue_flavors=""

    # Get number of resource types in file
    local count
    count=$(yq e '.resources | length' "$resources_file")

    for ((i = 0; i < count; i++)); do
        local name cpu memory
        name=$(yq e ".resources[$i].name" "$resources_file")
        cpu=$(yq e ".resources[$i].cpu" "$resources_file")
        memory=$(yq e ".resources[$i].memory" "$resources_file")

        echo "Processing flavor: $name (cpu=$cpu, memory=$memory)"

        resource_flavor_definitions+="---\napiVersion: kueue.x-k8s.io/v1beta1\nkind: ResourceFlavor\nmetadata:\n  name: $name\n"
        job_cluster_queue_flavors+="    - name: $name\n      resources:\n      - name: cpu\n        nominalQuota: $cpu\n      - name: memory\n        nominalQuota: $memory\n"
    done

    print_info "Applying ResourceFlavors..."
    cat <<EOF | kubectl_cmd apply -f -
$(echo -e "$resource_flavor_definitions")
EOF

    # Only apply batch queue on local manager cluster
    if [[ "$CLUSTER_MODE" = "local" ]]; then
        print_info "Applying batch LocalQueue..."
        cat <<EOF | kubectl_cmd apply -f -
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: LocalQueue
metadata:
  namespace: "default"
  name: "batch-queue"
spec:
  clusterQueue: "batch-queue"
EOF

        print_info "Applying batch ClusterQueue..."
        cat <<EOF | kubectl_cmd apply -f -
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: ClusterQueue
metadata:
  name: "batch-queue"
spec:
  namespaceSelector: {}
  resourceGroups:
  - coveredResources: ["cpu", "memory"]
    flavors:
    - name: "default"
      resources:
      - name: cpu
        nominalQuota: 2
      - name: memory
        nominalQuota: 3Gi
EOF
    fi

    print_info "Applying job LocalQueue..."
    cat <<EOF | kubectl_cmd apply -f -
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: LocalQueue
metadata:
  namespace: "default"
  name: "$node-job-queue"
spec:
  clusterQueue: "$node-job-queue"
EOF

    print_info "Applying job ClusterQueue..."
    local admission_checks=""

    if [[ "$CLUSTER_MODE" = "local" && "$node" != "local" ]]; then
        # Admission checks are only specified on the manager for remote job queues
        admission_checks="  admissionChecks:\n  - $node-job-admission-check"
    fi

    cat <<EOF | kubectl_cmd apply -f -
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: ClusterQueue
metadata:
  name: "$node-job-queue"
spec:
  namespaceSelector: {}
  resourceGroups:
  - coveredResources: ["cpu", "memory"]
    flavors:
$(echo -e "$job_cluster_queue_flavors")
$(echo -e "$admission_checks")
EOF

    # Only apply admission checks if in local mode
    if [[ "$CLUSTER_MODE" = "local" ]]; then
        print_info "Applying AdmissionCheck..."

        local parameters=""
        local controllerName=""
        if [[ "$node" = "local" ]]; then
            controllerName="kueue.x-k8s.io/provisioning-request"
            parameters="    kind: ProvisioningRequestConfig\n    name: provisioning-request-config"
        else
            controllerName="kueue.x-k8s.io/multikueue"
            parameters="    kind: MultiKueueConfig\n    name: $MULTIKUEUE_CONFIG"
        fi

        cat <<EOF | kubectl_cmd apply -f -
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: AdmissionCheck
metadata:
  name: $node-job-admission-check
spec:
  controllerName: $controllerName
  parameters:
    apiGroup: kueue.x-k8s.io
$(echo -e "$parameters")
EOF
    fi
}

connect_node() {
    if ! check_kueue_installed; then
        print_error "Kueue is not installed. Please run the 'install' command first."
        return 1
    fi

    if [[ "$CLUSTER_MODE" = "remote" ]]; then
        CLUSTER_MODE="local"
        if ! check_kueue_installed; then
            print_error "Kueue is not installed locally. Please run the 'install' command first."
            return 1
        fi
        CLUSTER_MODE="remote"
    fi

    # $REMOTE-resources.yaml if a remote is set, otherwise local-resources.yaml
    local resources_file="${REMOTE:-local}-resources.yaml"

    if [ ! -f "$resources_file" ]; then
        print_error "Resources file '$resources_file' not found. Please create it first."
        return 1
    fi

    ensure_reana_client_working

    # Apply resource file to manager (resources for remotes also need to be duplicated on the manager)
    print_section "📄 Applying resources manifest '$resources_file' to manager..."
    local original_cluster_mode="$CLUSTER_MODE"
    CLUSTER_MODE="local"
    if check_if_resources_already_applied "$resources_file"; then
        exit 1
    fi
    apply_resource_file "${REMOTE:-local}"
    CLUSTER_MODE="$original_cluster_mode"
    echo ""

    if [[ "$CLUSTER_MODE" = "remote" ]]; then
        # Also apply to remote if in remote mode
        print_section "📄 Applying resources manifest '$resources_file' to $REMOTE..."
        apply_resource_file "$REMOTE"

        # Create reana-secretsstore secret on remote
        print_section "📄 Copying secret to remote..."
        local user_id
        user_id=$(get_user_id)
        local secret_name="reana-secretsstore-$user_id"

        if kubectl_cmd get secret "$secret_name" &>/dev/null; then
            print_info "Secret already exists"
        else
            kubectl create secret generic "$secret_name" --dry-run=client -o yaml | kubectl_cmd apply -f -
        fi
    fi

    sleep 1
    echo ""
    print_status "Resources applied"
    echo ""

    if verify_kueue_resources "require-resources"; then
        if [[ "$CLUSTER_MODE" = "remote" ]]; then
            connect_remote_cluster
        fi
    else
        print_warning "Some Kueue resources are missing. Please check the output above."
    fi
}

# Handle workload removal/preservation
remove_workloads() {
    local workload_count
    workload_count=$(kubectl_cmd get workloads -A --no-headers 2>/dev/null | wc -l)

    print_section "🚧 Removing active Kueue workloads and associated jobs..."

    if [ "$workload_count" -gt 0 ]; then
        print_info "Found $workload_count workload(s), removing workloads and their parent jobs..."
        count_and_display_resources "workloads" "-A" "Active workloads"

        # First, find and remove the associated Jobs to prevent workload recreation
        print_info "Identifying and removing parent Jobs..."
        kubectl_cmd get jobs -A -o json 2>/dev/null | jq -r '.items[] | select(.metadata.labels["kueue.x-k8s.io/queue-name"] != null or .metadata.annotations["kueue.x-k8s.io/queue-name"] != null) | "\(.metadata.namespace) \(.metadata.name)"' | while read -r namespace job_name; do
            if [ -n "$namespace" ] && [ -n "$job_name" ]; then
                echo -e "${BLUE}   - Deleting Job $job_name in namespace $namespace...${NC}"
                kubectl_cmd delete job "$job_name" -n "$namespace" --ignore-not-found=true --timeout=30s
            fi
        done

        # Also remove any jobs that might have workloads associated (broader search)
        kubectl_cmd get workloads -A --no-headers 2>/dev/null | while read -r namespace workload_name rest; do
            # Extract potential job name from workload name (workloads are often named after their jobs)
            # Common pattern: job-<jobname>-<hash> becomes workload job-<jobname>-<hash>-<suffix>
            local potential_job_name
            if [[ "$workload_name" =~ ^(.+)-[a-f0-9]{5}$ ]]; then
                potential_job_name="${BASH_REMATCH[1]}"
            elif [[ "$workload_name" =~ ^(.+)-[a-f0-9]{8,}$ ]]; then
                potential_job_name="${BASH_REMATCH[1]}"
            else
                potential_job_name="$workload_name"
            fi

            # Check if a job with this name exists
            if kubectl_cmd get job "$potential_job_name" -n "$namespace" &>/dev/null; then
                echo -e "${BLUE}   - Deleting associated Job $potential_job_name in namespace $namespace...${NC}"
                kubectl_cmd delete job "$potential_job_name" -n "$namespace" --ignore-not-found=true --timeout=30s
            fi
        done

        # Now delete the workloads themselves
        print_info "Removing workloads..."
        delete_resources "workloads" "" ""

        # Wait for workload cleanup
        print_info "Waiting for workload and job cleanup..."
        local cleanup_timeout=60
        local count=0
        while [ $count -lt $cleanup_timeout ]; do
            local remaining_workloads
            remaining_workloads=$(kubectl_cmd get workloads -A --no-headers 2>/dev/null | wc -l)
            local remaining_kueue_jobs
            remaining_kueue_jobs=$(kubectl_cmd get jobs -A -o json 2>/dev/null | jq -r '.items[] | select(.metadata.labels["kueue.x-k8s.io/queue-name"] != null or .metadata.annotations["kueue.x-k8s.io/queue-name"] != null)' 2>/dev/null | jq -s length 2>/dev/null || echo "0")

            if [ "$remaining_workloads" -eq 0 ] && [ "$remaining_kueue_jobs" -eq 0 ]; then
                break
            fi

            if [ $((count % 10)) -eq 0 ]; then
                print_info "Still waiting... Workloads: $remaining_workloads, Kueue Jobs: $remaining_kueue_jobs"
            fi

            sleep 1
            ((count++))
        done

        # Force cleanup if needed
        local remaining
        remaining=$(kubectl_cmd get workloads -A --no-headers 2>/dev/null | wc -l)

        if [ "$remaining" -gt 0 ]; then
            print_warning "Some workloads still exist, forcing deletion..."
            force_delete_resources "workloads" "" "-A"

            # Force delete any remaining Kueue jobs
            kubectl_cmd get jobs -A -o json 2>/dev/null | jq -r '.items[] | select(.metadata.labels["kueue.x-k8s.io/queue-name"] != null or .metadata.annotations["kueue.x-k8s.io/queue-name"] != null) | "\(.metadata.namespace) \(.metadata.name)"' | while read -r namespace job_name; do
                if [ -n "$namespace" ] && [ -n "$job_name" ]; then
                    echo -e "${BLUE}   - Force deleting Job $job_name in namespace $namespace...${NC}"
                    kubectl_cmd patch job "$job_name" -n "$namespace" --type merge --patch '{"metadata":{"finalizers":[]}}' 2>/dev/null || true
                    kubectl_cmd delete job "$job_name" -n "$namespace" --force --grace-period=0 --ignore-not-found=true 2>/dev/null || true
                fi
            done
        fi

        # Final check
        remaining=$(kubectl_cmd get workloads -A --no-headers 2>/dev/null | wc -l)
        local remaining_jobs
        remaining_jobs=$(kubectl_cmd get jobs -A -o json 2>/dev/null | jq -r '.items[] | select(.metadata.labels["kueue.x-k8s.io/queue-name"] != null or .metadata.annotations["kueue.x-k8s.io/queue-name"] != null)' 2>/dev/null | jq -s length 2>/dev/null || echo "0")

        if [ "$remaining" -eq 0 ] && [ "$remaining_jobs" -eq 0 ]; then
            print_status "All workloads and associated jobs removed"
        else
            print_warning "$remaining workloads and $remaining_jobs Kueue jobs still exist after cleanup"
            if [ "$remaining" -gt 0 ]; then
                print_info "Remaining workloads:"
                kubectl_cmd get workloads -A 2>/dev/null || true
            fi
            if [ "$remaining_jobs" -gt 0 ]; then
                print_info "Remaining Kueue jobs:"
                kubectl_cmd get jobs -A -o json 2>/dev/null | jq -r '.items[] | select(.metadata.labels["kueue.x-k8s.io/queue-name"] != null or .metadata.annotations["kueue.x-k8s.io/queue-name"] != null) | "\(.metadata.namespace)\t\(.metadata.name)"' 2>/dev/null || true
            fi
        fi
    else
        print_status "No active workloads found"
    fi
}

# Remove Kueue resources (queues, flavors, etc.)
remove_kueue_resources() {
    print_section "📄 Removing Kueue resource manifests..."

    # Delete any remaining LocalQueues
    print_section " - Removing LocalQueues..."
    force_delete_resources "localqueue" "" ""

    # Delete any remaining ClusterQueues
    print_section " - Removing ClusterQueues..."
    force_delete_resources "clusterqueue" "" ""

    # Delete ResourceFlavors
    print_section " - Removing ResourceFlavors..."
    force_delete_resources "resourceflavor" "" ""

    # Delete AdmissionChecks
    print_section " - Removing AdmissionChecks..."
    force_delete_resources "admissioncheck" "" ""

    # Delete MultiKueueClusters
    print_section " - Removing MultiKueueCluster..."
    force_delete_resources "multikueuecluster" "" "-n kueue-system"

    # Delete MultiKueueConfigs
    print_section " - Removing MultiKueueConfig..."
    force_delete_resources "multikueueconfig" "" "-n kueue-system"

    # Delete Secrets
    print_section " - Removing Secret..."
    force_delete_resources "secret" "" "-n kueue-system"

    print_status "Kueue resources removed"
}

# Remove Kueue helm installation
remove_kueue_installation() {
    if ! check_kueue_installed; then
        return 0
    fi

    print_section "📦 Uninstalling Kueue..."
    if ! helm_cmd uninstall kueue -n kueue-system --wait --timeout 10s; then
        # Check if error was a timeout
        if helm_cmd status kueue -n kueue-system >/dev/null 2>&1; then
            print_warning "Helm uninstall timed out, retrying again..."
            helm_cmd uninstall kueue -n kueue-system --wait --timeout 10s
            print_status "Kueue uninstalled successfully"
        else
            print_status "Release already gone"
        fi
    fi

    print_section " - Removing Kueue namespace..."
    force_delete_resources "namespace" "" "kueue-system"
}

# Main remove function with granular options
remove_kueue() {
    print_section "🗑️ Removing Kueue components..."

    # Determine what to remove based on flags
    local should_remove_workloads=$REMOVE_WORKLOADS
    local should_remove_resources=$REMOVE_RESOURCES
    local should_remove_kueue=$REMOVE_KUEUE

    # If --all is specified, remove everything
    if [ "$REMOVE_ALL" = "true" ]; then
        should_remove_workloads=true
        should_remove_resources=true
        should_remove_kueue=true
    fi

    # If no specific flags are set, default to the original behavior (remove all)
    if [ "$REMOVE_WORKLOADS" = "false" ] && [ "$REMOVE_RESOURCES" = "false" ] &&
        [ "$REMOVE_KUEUE" = "false" ] &&
        [ "$REMOVE_ALL" = "false" ]; then
        should_remove_workloads=true
        should_remove_resources=true
        should_remove_kueue=true
    fi

    # Show what will be removed
    print_info "Components to be removed:"
    [ "$should_remove_workloads" = "true" ] && echo -e "${BLUE}  • Workloads${NC}"
    [ "$should_remove_resources" = "true" ] && echo -e "${BLUE}  • Kueue resources (queues, flavors)${NC}"
    [ "$should_remove_kueue" = "true" ] && echo -e "${BLUE}  • Kueue installation (Helm chart)${NC}"
    echo

    # Remove workloads first if requested
    if [ "$should_remove_workloads" = "true" ]; then
        remove_workloads
    fi

    # Remove Kueue resources if requested
    if [ "$should_remove_resources" = "true" ]; then
        remove_kueue_resources
    fi

    # Remove Kueue installation if requested
    if [ "$should_remove_kueue" = "true" ]; then
        remove_kueue_installation
    fi

    # Final resource check if everything was supposed to be removed
    if [ "$should_remove_workloads" = "true" ] && [ "$should_remove_resources" = "true" ] &&
        [ "$should_remove_kueue" = "true" ]; then
        if verify_kueue_resources "require-no-resources"; then
            print_warning "Some Kueue resources may still exist"
        else
            print_status "All Kueue resources removed"
        fi
    fi

    print_status "Kueue removal completed"
}

handle_remove() {
    # Build confirmation message based on what will be removed
    local confirm_msg="Are you sure you want to remove the following Kueue components?"
    local components=""

    # Determine what will be removed
    local will_remove_resources=$REMOVE_RESOURCES
    local will_remove_kueue=$REMOVE_KUEUE
    local will_remove_workloads=$REMOVE_WORKLOADS

    if [ "$REMOVE_ALL" = "true" ]; then
        will_remove_resources=true
        will_remove_kueue=true
        will_remove_workloads=true
    fi

    # If no specific flags, default to all
    if [ "$REMOVE_WORKLOADS" = "false" ] && [ "$REMOVE_RESOURCES" = "false" ] &&
        [ "$REMOVE_KUEUE" = "false" ] &&
        [ "$REMOVE_ALL" = "false" ]; then
        will_remove_resources=true
        will_remove_kueue=true
        will_remove_workloads=true
    fi

    # Build component list
    [ "$will_remove_resources" = "true" ] && components="${components}\n  • Kueue resources (queues, flavors)"
    [ "$will_remove_kueue" = "true" ] && components="${components}\n  • Kueue installation (Helm chart and namespace)"
    [ "$will_remove_workloads" = "true" ] && components="${components}\n  • Workloads"

    echo -e "$confirm_msg$components"
    echo ""
    read -rp "Continue? (y/N): " CONFIRM
    if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
        remove_kueue
    else
        echo "Removal cancelled."
        exit 0
    fi
}

check_crds_installed() {
    local print_output="$1"

    local kueue_crds=("clusterqueues.kueue.x-k8s.io" "localqueues.kueue.x-k8s.io" "resourceflavors.kueue.x-k8s.io" "workloads.kueue.x-k8s.io" "admissionchecks.kueue.x-k8s.io" "multikueueconfigs.kueue.x-k8s.io" "multikueueclusters.kueue.x-k8s.io")
    local crd_count=0

    for crd in "${kueue_crds[@]}"; do
        if kubectl_cmd get crd "$crd" &>/dev/null; then
            local version
            version=$(kubectl_cmd get crd "$crd" -o jsonpath='{.spec.versions[0].name}' 2>/dev/null || echo "unknown")
            if [ "$print_output" = "true" ]; then
                print_status "$crd (version: $version)"
            fi
            ((crd_count++))
        else
            if [ "$print_output" = "true" ]; then
                print_error "$crd - not found"
            fi
        fi
    done

    if [ $crd_count -eq ${#kueue_crds[@]} ]; then
        return 0
    else
        return 1
    fi
}

connect_remote_cluster() {
    # Configure Kueue to work with minimal workload types only.
    # This seems to be required for MultiKueue to work?
    echo -e "${BLUE}⚙️  Configuring Kueue for minimal workload types...${NC}"

    # Create ConfigMap to disable external integrations validation
    echo -e "${YELLOW}$ kubectl create configmap kueue-manager-config -n kueue-system --from-literal=controller_manager_config.yaml='<YAML_CONFIG>' --dry-run=client -o yaml | kubectl apply -f -${NC}"
    kubectl create configmap kueue-manager-config -n kueue-system --from-literal=controller_manager_config.yaml='
    apiVersion: config.kueue.x-k8s.io/v1beta1
    kind: Configuration
    namespace: kueue-system
    health:
      healthProbeBindAddress: :8081
    metrics:
      bindAddress: :8080
    webhook:
      port: 9443
    leaderElection:
      leaderElect: true
      resourceName: c1f6bfd2.kueue.x-k8s.io
    controller:
      groupKindConcurrency:
        Job.batch: 5
        Pod.v1: 5
        Workload.kueue.x-k8s.io: 5
        LocalQueue.kueue.x-k8s.io: 1
        ClusterQueue.kueue.x-k8s.io: 1
        ResourceFlavor.kueue.x-k8s.io: 1
        AdmissionCheck.kueue.x-k8s.io: 1
    integrations:
      frameworks:
        - "batch/job"
      podOptions:
        namespaceSelector:
          matchExpressions:
          - key: kubernetes.io/metadata.name
            operator: NotIn
            values: [ kube-system, kueue-system ]
    ' --dry-run=client -o yaml | kubectl apply -f -

    # Restart Kueue controller to pick up the new config
    run_cmd kubectl rollout restart deployment/kueue-controller-manager -n kueue-system

    print_status "Kueue configured for minimal workload types (Jobs only)"

    print_section "🔗 Connecting to Remote Cluster..."

    local secret_name
    secret_name=$(get_secret_name "$REMOTE")

    # Check if secret already exists
    if kubectl get secret "$secret_name" -n kueue-system &>/dev/null; then
        print_warning "Secret $secret_name already exists. Overwriting..."
    else
        print_info "Creating secret $secret_name"
    fi

    kubectl create secret generic "$secret_name" -n kueue-system \
        --from-file=kubeconfig="$REMOTE_KUBECONFIG" \
        --dry-run=client -o yaml | kubectl apply -f -

    print_status "Remote cluster secret created in manager cluster."
    echo ""

    create_multikueue_cluster "$REMOTE" "$secret_name"
}

create_multikueue_cluster() {
    local node="$1"
    local secret_name="$2"

    # Create MultiKueueCluster
    print_info "Creating MultiKueueCluster..."
    local mk_cluster_name
    mk_cluster_name=$(get_multikueue_cluster_name "$node")

    # Only include secret if node is not local
    local spec=""
    if [[ "$node" != "local" ]]; then
        spec="spec:\n  kubeConfig:\n    locationType: Secret\n    location: $secret_name"
    fi

    run_cmd kubectl apply -f - <<EOF
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: MultiKueueCluster
metadata:
  name: $mk_cluster_name
  namespace: kueue-system
$(echo -e "$spec")
EOF

    if kubectl get multikueueconfig "$MULTIKUEUE_CONFIG" -n kueue-system >/dev/null 2>&1; then
        # Check if node already exists in multikueueconfig
        if kubectl get multikueueconfig "$MULTIKUEUE_CONFIG" -n kueue-system -o jsonpath='{.spec.clusters}' | grep -q "$mk_cluster_name"; then
            print_info "Node $node already exists in MultiKueueConfig. Skipping..."
        else
            print_info "MultiKueueConfig already exists. Patching..."
            # multikueueconfig exists: append new cluster
            kubectl patch multikueueconfig "$MULTIKUEUE_CONFIG" \
                -n kueue-system \
                --type='json' \
                -p "[{\"op\": \"add\", \"path\": \"/spec/clusters/-\", \"value\": \"$mk_cluster_name\"}]"
        fi
    else
        # multikueueconfig doesn't exist: create fresh config
        print_info "Creating MultiKueueConfig..."
        kubectl apply -f - <<EOF
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: MultiKueueConfig
metadata:
  name: $MULTIKUEUE_CONFIG
  namespace: kueue-system
spec:
  clusters:
  - $mk_cluster_name
EOF
    fi

    print_status "MultiKueueCluster connection created."
}

disconnect_node() {
    print_section "🔌 Disconnecting Node..."

    local resources_file="$REMOTE-resources.yaml"

    # Temporarily unset REMOTE_KUBECONFIG while we delete resources from the manager
    local temp_kubeconfig="$REMOTE_KUBECONFIG"
    REMOTE_KUBECONFIG=""

    local resources_count
    resources_count=$(yq e '.resources | length' "$resources_file")

    # Remove job queue resources on the manager
    force_delete_resources "localqueue" "$REMOTE-job-queue" ""
    force_delete_resources "clusterqueue" "$REMOTE-job-queue" ""
    force_delete_resources "admissioncheck" "$REMOTE-job-admission-check" ""

    for ((i = 0; i < resources_count; i++)); do
        local name
        name=$(yq e ".resources[$i].name" "$resources_file")
        force_delete_resources "resourceflavor" "$name" ""
    done

    # Restore REMOTE_KUBECONFIG
    REMOTE_KUBECONFIG="$temp_kubeconfig"

    if [[ "$CLUSTER_MODE" = "remote" ]]; then
        # Remove job queue resources on the remote
        force_delete_resources "localqueue" "$REMOTE-job-queue" ""
        force_delete_resources "clusterqueue" "$REMOTE-job-queue" ""
        force_delete_resources "admissioncheck" "$REMOTE-job-admission-check" ""

        for ((i = 0; i < resources_count; i++)); do
            local name
            name=$(yq e ".resources[$i].name" "$resources_file")
            force_delete_resources "resourceflavor" "$name" ""
        done

        # Temporarily unset REMOTE_KUBECONFIG while we remove the
        # multikueuecluster, secret, and remove the node from multikueueconfig
        local temp_kubeconfig="$REMOTE_KUBECONFIG"
        REMOTE_KUBECONFIG=""

        local secret_name
        secret_name=$(get_secret_name "$REMOTE")
        local mk_cluster_name
        mk_cluster_name=$(get_multikueue_cluster_name "$REMOTE")

        # Remove MultiKueue resources
        print_info "Removing MultiKueue resources..."
        force_delete_resources "multikueuecluster" "$mk_cluster_name" "-n kueue-system"
        force_delete_resources "secret" "$secret_name" "-n kueue-system"

        # Amend MultiKueueConfig to remove reference to multikueue cluster
        if kubectl get multikueueconfig "$MULTIKUEUE_CONFIG" -n kueue-system >/dev/null 2>&1; then
            print_info "Patching MultiKueueConfig to remove reference to $REMOTE..."
            kubectl patch multikueueconfig "$MULTIKUEUE_CONFIG" \
                -n kueue-system \
                --type='json' \
                -p "[{\"op\": \"remove\", \"path\": \"/spec/clusters\", \"value\": [\"$mk_cluster_name\"]}]" || true
        fi

        # Restore REMOTE_KUBECONFIG
        REMOTE_KUBECONFIG="$temp_kubeconfig"

        print_status "Remote cluster disconnected successfully"
    fi
}

show_kueue_status() {
    print_section "📊 Kueue Status Report$(if [[ "$CLUSTER_MODE" = "remote" ]]; then echo " ($REMOTE)"; fi)"
    echo ""

    # Check Kueue installation
    print_section "🔧 Installation Status"
    if check_kueue_installed; then
        print_info "Pod status in kueue-system:"
        kubectl_cmd get pods -n kueue-system --no-headers 2>/dev/null | while read -r name ready status age; do
            if [[ "$status" == "Running" ]]; then
                print_status "$name: $status ($ready ready)"
            else
                print_warning "$name: $status ($ready ready)"
            fi
        done
    fi
    echo ""

    # Check CRDs
    print_section "📋 Custom Resource Definitions (CRDs)"
    if check_crds_installed "true"; then
        print_status "All Kueue CRDs are present"
    else
        print_warning "Some Kueue CRDs are missing"
    fi
    echo ""

    # Check ResourceFlavors
    local rf_count
    rf_count=$(kubectl_cmd get resourceflavors --no-headers 2>/dev/null | wc -l)
    rf_count=$(echo "$rf_count" | tr -d '[:space:]')
    print_section "🎨 ResourceFlavors ($rf_count)"

    if [[ "$rf_count" -gt 0 ]]; then
        kubectl_cmd get resourceflavors --no-headers 2>/dev/null | while read -r name age; do
            echo -e "${WHITE}   • $name (age: $age)${NC}"
        done
    else
        print_warning "No ResourceFlavors found"
    fi
    echo ""

    # Check LocalQueues
    local lq_count
    lq_count=$(kubectl_cmd get localqueues -A --no-headers 2>/dev/null | wc -l)
    lq_count=$(echo "$lq_count" | tr -d '[:space:]')
    print_section "🏪 LocalQueues ($lq_count)"

    if [[ "$lq_count" -gt 0 ]]; then
        kubectl_cmd get localqueues -A -o custom-columns="NAMESPACE:.metadata.namespace,NAME:.metadata.name,CLUSTERQUEUE:.spec.clusterQueue,PENDING:.status.pendingWorkloads,ADMITTED:.status.admittedWorkloads" --no-headers 2>/dev/null | while read -r line; do
            echo -e "${WHITE}   • $line${NC}"
        done
    else
        print_warning "No LocalQueues found"
    fi
    echo ""

    # Check ClusterQueues
    local cq_count
    cq_count=$(kubectl_cmd get clusterqueues --no-headers 2>/dev/null | wc -l)
    cq_count=$(echo "$cq_count" | tr -d '[:space:]')
    print_section "🏢 ClusterQueues ($cq_count)"

    if [[ "$cq_count" -gt 0 ]]; then
        kubectl_cmd get clusterqueues -o custom-columns="NAME:.metadata.name,COHORT:.spec.cohort,PENDING:.status.pendingWorkloads,ADMITTED:.status.admittedWorkloads" --no-headers 2>/dev/null | while read -r line; do
            echo -e "${WHITE}   • $line${NC}"
        done

        echo ""
        print_info "Resource quotas per ClusterQueue:"
        kubectl_cmd get clusterqueues -o json 2>/dev/null | jq -r '.items[] | "\(.metadata.name): " + (.spec.resourceGroups[0].flavors[0].resources | map("\(.name)=\(.nominalQuota)") | join(", "))' | while read -r line; do
            echo -e "   📊 $line"
        done
    else
        print_warning "No ClusterQueues found"
    fi
    echo ""

    # Check active Workloads
    print_section "⚡ Active Workloads"
    local workload_count
    workload_count=$(kubectl_cmd get workloads -A --no-headers 2>/dev/null | wc -l)

    if [[ "$workload_count" -gt 0 ]]; then
        print_info "Found $workload_count active workload(s):"
        kubectl_cmd get workloads -A -o custom-columns="NAMESPACE:.metadata.namespace,NAME:.metadata.name,QUEUE:.spec.queueName,ADMITTED:.status.conditions[?(@.type=='Admitted')].status" --no-headers 2>/dev/null | while read -r line; do
            if [[ "$line" == *"True"* ]]; then
                echo -e "${GREEN}   ✅ $line${NC}"
            else
                echo -e "${YELLOW}   ⏳ $line${NC}"
            fi
        done
    else
        print_info "No active workloads"
    fi
    echo ""

    # Check Kueue-managed Jobs
    print_section "🎯 Kueue-managed Jobs"
    local kueue_jobs
    kueue_jobs=$(kubectl_cmd get jobs -A -o json 2>/dev/null | jq -r '.items[] | select(.metadata.labels["kueue.x-k8s.io/queue-name"] != null or .metadata.annotations["kueue.x-k8s.io/queue-name"] != null)' 2>/dev/null | jq -s length 2>/dev/null || echo "0")

    if [[ "$kueue_jobs" -gt 0 ]]; then
        print_info "Found $kueue_jobs Kueue-managed job(s):"
        kubectl_cmd get jobs -A -o json 2>/dev/null | jq -r '.items[] | select(.metadata.labels["kueue.x-k8s.io/queue-name"] != null or .metadata.annotations["kueue.x-k8s.io/queue-name"] != null) | "\(.metadata.namespace) \(.metadata.name) \(.metadata.labels["kueue.x-k8s.io/queue-name"] // .metadata.annotations["kueue.x-k8s.io/queue-name"] // "N/A") \(.status.conditions[-1].type // "Unknown")"' 2>/dev/null | while read -r namespace name queue status; do
            case "$status" in
            "Complete") print_status "$namespace/$name (queue: $queue, status: $status)${NC}" ;;
            "Failed") print_error "$namespace/$name (queue: $queue, status: $status)${NC}" ;;
            *) print_warning "$namespace/$name (queue: $queue, status: $status)${NC}" ;;
            esac
        done
    else
        print_info "No Kueue-managed jobs found"
    fi
    echo ""

    # Check recent Kueue events
    print_section "📰 Recent Kueue Events (last 10)"
    local events
    events=$(kubectl_cmd get events -A --field-selector reason=Admitted,reason=QuotaReserved,reason=Preempted,reason=Evicted --sort-by='.lastTimestamp' 2>/dev/null | tail -10)

    if [[ -n "$events" && "$events" != *"No resources found"* ]]; then
        echo "$events" | while IFS= read -r line; do
            case "$line" in
            *"LAST SEEN"*) echo -e "${BLUE}$line${NC}" ;;
            *"Admitted"*) echo -e "${GREEN}$line${NC}" ;;
            *"Preempted"* | *"Evicted"*) echo -e "${RED}$line${NC}" ;;
            *) echo -e "${YELLOW}$line${NC}" ;;
            esac
        done
    else
        print_info "No recent Kueue events found"
    fi
    echo ""

    # Check connections to remote clusters (local mode only)
    local problems_with_remotes=false
    if [[ "$CLUSTER_MODE" = "local" ]]; then
        print_section "📋 Detected Kubeconfigs"
        local kubeconfigs
        kubeconfigs=$(find_kubeconfigs)
        if [[ -n "$kubeconfigs" ]]; then
            echo "$kubeconfigs" | tr ',' '\n' | while read -r kubeconfig; do
                echo -e "${WHITE}   • $kubeconfig-kubeconfig.yaml${NC}"
            done
        else
            print_info "No kubeconfigs found"
        fi
        echo ""

        print_section "📋 Detected Resource Manifests"
        local resources_files
        resources_files=$(find_resources_files)
        if [[ -n "$resources_files" ]]; then
            echo "$resources_files" | tr ',' '\n' | while read -r resources_file; do
                local resources_file_name
                resources_file_name=$(basename "$resources_file")
                echo -e "${WHITE}   • $resources_file_name${NC}"

                local count
                count=$(yq e '.resources | length' "$resources_file")

                if [[ "$count" -gt 0 ]]; then
                    for ((i = 0; i < count; i++)); do
                        local name cpu memory

                        name=$(yq e ".resources[$i].name" "$resources_file")
                        cpu=$(yq e ".resources[$i].cpu" "$resources_file")
                        memory=$(yq e ".resources[$i].memory" "$resources_file")

                        echo -e "${BLUE}     - $name: cpu=$cpu, memory=$memory${NC}"
                    done
                else
                    print_warning "No resources defined in $resources_file_name"
                fi
            done
        else
            print_info "No resource manifests found"
        fi
        echo ""

        print_section "🔗 Available Remotes"
        local configured_remotes=()
        if [[ -n "$REMOTES" ]]; then
            # Get list of fully configured remotes
            while read -r remote; do
                local has_config=false
                local has_cluster=false
                local has_secret=false

                # Check for multikueueconfig
                if kubectl get multikueueconfigs "$MULTIKUEUE_CONFIG" -n kueue-system >/dev/null 2>&1; then
                    has_config=true
                fi

                # Check for multikueuecluster
                local mk_cluster_name
                mk_cluster_name=$(get_multikueue_cluster_name "$remote")
                if kubectl get multikueueclusters "$mk_cluster_name" -n kueue-system >/dev/null 2>&1; then
                    has_cluster=true
                fi

                # Check for secret
                local secret_name
                secret_name=$(get_secret_name "$remote")
                if kubectl get secret "$secret_name" -n kueue-system >/dev/null 2>&1; then
                    has_secret=true
                fi

                # Only add to configured list if all three resources exist
                if $has_config && $has_cluster && $has_secret; then
                    configured_remotes+=("$remote")
                fi
            done <<<"$(echo "$REMOTES" | tr ',' '\n')"

            local some_unreachable=false
            local some_kueue_not_installed=false

            while read -r remote; do
                # Check if remote is configured
                local is_configured=false
                for configured in "${configured_remotes[@]}"; do
                    if [[ "$configured" == "$remote" ]]; then
                        is_configured=true
                        break
                    fi
                done

                # Check reachability and display with appropriate color
                if kubectl --kubeconfig="$remote-kubeconfig.yaml" get namespaces >/dev/null 2>&1; then
                    # Check if Kueue is installed
                    local temp_cluster_mode="$CLUSTER_MODE"
                    local temp_remote_kubeconfig="$REMOTE_KUBECONFIG"
                    CLUSTER_MODE="remote"
                    REMOTE_KUBECONFIG="$remote-kubeconfig.yaml"
                    if check_kueue_installed "quiet"; then
                        if $is_configured; then
                            echo -e "${GREEN}   ✓ $remote (connected)${NC}"

                            # Check if there are ResourceFlavors applied on the remote cluster that are not applied to the local manager cluster
                            local remote_rfs
                            remote_rfs=$(kubectl --kubeconfig="$remote-kubeconfig.yaml" get resourceflavors --no-headers 2>/dev/null | awk '{print $1}')
                            while read -r rf; do
                                if ! kubectl get resourceflavors "$rf" >/dev/null 2>&1; then
                                    print_warning "ResourceFlavor '$rf' is defined on remote '$remote' but not applied to the local manager cluster"
                                fi
                            done <<<"$(echo "$remote_rfs" | tr ',' '\n')"
                        else
                            echo -e "${WHITE}   • $remote (reachable, not connected)${NC}"
                        fi
                    else
                        echo -e "${YELLOW}   • $remote (reachable, Kueue not installed)${NC}"
                        some_kueue_not_installed=true
                    fi
                    CLUSTER_MODE="$temp_cluster_mode"
                    REMOTE_KUBECONFIG="$temp_remote_kubeconfig"
                else
                    echo -e "${RED}   ✗ $remote (unreachable)${NC}"
                    some_unreachable=true
                fi
            done <<<"$(echo "$REMOTES" | tr ',' '\n')"

            # Summary messages
            if $some_unreachable; then
                print_warning "Some remotes are unreachable. Please make sure the kubeconfigs are correct."
                problems_with_remotes=true
            elif $some_kueue_not_installed; then
                print_warning "Some remotes do not have Kueue installed. Please install Kueue before connecting them."
                problems_with_remotes=true
            fi
        else
            print_info "No remotes found"
        fi
        echo ""
    fi

    # Validate Kueue setup in values.yaml (local mode only)
    local kueue_enabled_in_config=false
    if [[ "$CLUSTER_MODE" = "local" ]]; then
        print_section "⚙️  Configuration Check"
        local values_file
        values_file="$(dirname "$0")/../helm/reana/values.yaml"

        # Check if local-resources.yaml exists
        if [[ ! -f "local-resources.yaml" ]]; then
            print_warning "No local-resources.yaml found. Jobs will not be able to run locally."
            echo ""
        else
            print_status "local-resources.yaml exists."
        fi

        if [[ -f "$values_file" ]]; then
            # Check if Kueue is enabled
            if grep -q "kueue:" "$values_file" && grep -A1 "kueue:" "$values_file" | grep -q "enabled: true"; then
                print_status "Kueue is enabled in values.yaml"
                kueue_enabled_in_config=true
            else
                print_warning "Kueue is not enabled in values.yaml"
            fi

            # Check if all queues listed in values.yaml are connected
            local listed_queues
            listed_queues=$(yq e '.kueue.queues[].name' "$values_file")
            local missing_queues=false
            while read -r queue; do
                if ! echo "${configured_remotes[@]}" | grep -q "$queue"; then
                    print_warning "Queue '$queue' is listed in values.yaml but not connected"
                    missing_queues=true
                fi
            done <<<"$(echo "$listed_queues" | tr ',' '\n')"
            if ! $missing_queues; then
                print_status "All listed queues are connected"
            fi
        else
            print_error "values.yaml file not found at $values_file"
        fi
        echo ""
    fi

    # Summary
    print_section "📝 Summary"
    if check_kueue_installed; then
        local rf_count
        rf_count=$(kubectl_cmd get resourceflavors --no-headers 2>/dev/null | wc -l 2>/dev/null || echo "0")
        rf_count=$(echo "$rf_count" | tr -d '[:space:]')

        local lq_count
        lq_count=$(kubectl_cmd get localqueues -A --no-headers 2>/dev/null | wc -l 2>/dev/null || echo "0")
        lq_count=$(echo "$lq_count" | tr -d '[:space:]')

        local cq_count
        cq_count=$(kubectl_cmd get clusterqueues --no-headers 2>/dev/null | wc -l 2>/dev/null || echo "0")
        cq_count=$(echo "$cq_count" | tr -d '[:space:]')

        local wl_count
        wl_count=$(kubectl_cmd get workloads -A --no-headers 2>/dev/null | wc -l 2>/dev/null || echo "0")
        wl_count=$(echo "$wl_count" | tr -d '[:space:]')

        # Build summary message
        local summary="Kueue is configured with $rf_count ResourceFlavor(s), $lq_count LocalQueue(s), $cq_count ClusterQueue(s)"

        # Check if properly configured (skip queue checks for filtered modes)
        local properly_configured=true
        if [[ "$rf_count" -eq 0 || "$lq_count" -eq 0 || "$cq_count" -eq 0 ]]; then
            properly_configured=false
        fi

        if $properly_configured; then
            if [[ "$CLUSTER_MODE" = "local" ]]; then
                if $kueue_enabled_in_config; then
                    print_status "$summary and is enabled in config"
                else
                    print_warning "$summary but is not enabled in values.yaml. Enable it and redeploy to use Kueue."
                fi
            else
                print_status "$summary"
            fi

            if $problems_with_remotes; then
                print_warning "Some remotes are unreachable or have issues."
            fi

            if [[ "$wl_count" -gt 0 ]]; then
                print_info "Currently processing $wl_count workload(s)"
            else
                print_info "No active workloads"
            fi
        else
            print_warning "Connection to remote workers still required. Available remotes: $REMOTES"
        fi
    else
        local install_cmd="'$0 install"
        [[ "$CLUSTER_MODE" = "remote" ]] && install_cmd+=" --remote"
        install_cmd+="'"
        print_info "Run $install_cmd to install Kueue"
    fi
}

check_remote_cluster_connection() {
    local errors_present=false
    print_section "🔍 Checking Remote MultiKueue Setup"
    echo ""

    local secret_name
    secret_name=$(get_secret_name "$REMOTE")
    local mk_cluster_name
    mk_cluster_name=$(get_multikueue_cluster_name "$REMOTE")

    # Test direct connection to remote cluster
    if ! run_cmd kubectl --kubeconfig="$REMOTE_KUBECONFIG" get namespaces >/dev/null 2>&1; then
        print_error "Cannot connect to remote cluster using remote kubeconfig."
        errors_present=true
    else
        print_status "Remote cluster is reachable with remote kubeconfig."
    fi

    # Verify that the same namespace exists here and on the remote cluster
    print_info "Verifying Namespace setup..."
    if ! kubectl get namespace default >/dev/null 2>&1; then
        print_error "Namespace 'default' not found on manager cluster."
        errors_present=true
    fi
    if ! kubectl --kubeconfig="$REMOTE_KUBECONFIG" get namespace default >/dev/null 2>&1; then
        print_error "Namespace 'default' not found on remote cluster."
        errors_present=true
    fi

    # Verify remote secret exists
    print_info "Checking for remote secret..."
    if ! kubectl get secret "$secret_name" -n kueue-system >/dev/null 2>&1; then
        print_error "Secret '$secret_name' not found in manager cluster."
        errors_present=true
    else
        print_status "Secret '$secret_name' found."
        # Test if secret works by extracting kubeconfig and trying a command
        local tmp_kubeconfig
        tmp_kubeconfig=$(mktemp)
        kubectl get secret "$secret_name" -n kueue-system -o jsonpath='{.data.kubeconfig}' | base64 -d >"$tmp_kubeconfig"
        if ! kubectl --kubeconfig="$tmp_kubeconfig" get namespaces >/dev/null 2>&1; then
            print_error "Secret '$secret_name' exists but kubeconfig inside is invalid."
            errors_present=true
        else
            print_status "Secret '$secret_name' contains a working kubeconfig."
        fi
        rm -f "$tmp_kubeconfig"
    fi

    # Verify AdmissionChecks
    print_info "Checking AdmissionChecks..."
    local ac_count
    ac_count=$(kubectl get admissioncheck --no-headers 2>/dev/null | wc -l || echo 0)
    if [ "$ac_count" -eq 0 ]; then
        print_error "No AdmissionChecks found — workloads will never be admitted."
        errors_present=true
    else
        print_status "$ac_count AdmissionCheck(s) present."
    fi

    # Verify MultiKueueCluster
    print_info "Checking MultiKueueCluster..."
    if ! kubectl get multikueuecluster "$mk_cluster_name" >/dev/null 2>&1; then
        print_error "MultiKueueCluster '$mk_cluster_name' not found."
        errors_present=true
    else
        print_status "MultiKueueCluster '$mk_cluster_name' exists."
    fi

    # Verify MultiKueueConfig
    print_info "Checking MultiKueueConfig..."
    if ! kubectl get multikueueconfig "$MULTIKUEUE_CONFIG" -n kueue-system >/dev/null 2>&1; then
        print_error "MultiKueueConfig '$MULTIKUEUE_CONFIG' not found in namespace kueue-system."
        errors_present=true
    else
        print_status "MultiKueueConfig exists in namespace kueue-system."
    fi

    if [ "$errors_present" = "true" ]; then
        return 1
    else
        return 0
    fi
}

# Monitor Kueue
monitor_kueue() {
    while true; do
        clear
        echo "========================================"
        echo "  KUEUE WORKLOAD MONITORING - $(date +%H:%M:%S)"
        echo "========================================"
        echo
        echo "=== Kueue Workloads ==="
        kubectl_cmd get workloads -A 2>/dev/null || echo "No workloads found"
        echo
        echo "=== Jobs with Kueue Labels/Annotations ==="
        kubectl_cmd get jobs -A -o json 2>/dev/null | jq -r '.items[] | select(.metadata.labels["kueue.x-k8s.io/queue-name"] != null or .metadata.annotations["kueue.x-k8s.io/queue-name"] != null) | "\(.metadata.namespace)\t\(.metadata.name)\t\(.metadata.labels["kueue.x-k8s.io/queue-name"] // .metadata.annotations["kueue.x-k8s.io/queue-name"] // "N/A")"' 2>/dev/null || echo "No Kueue-managed jobs"
        echo
        echo "=== Queue Status ==="
        kubectl_cmd get localqueues,clusterqueues -A 2>/dev/null
        echo
        echo "=== Recent Events (Kueue-related) ==="
        kubectl_cmd get events -A --field-selector reason=Admitted,reason=QuotaReserved,reason=Preempted --sort-by='.lastTimestamp' 2>/dev/null | tail -5
        sleep "${MONITOR_REFRESH_INTERVAL_SECS}s"
    done
}

validate_num_greater_than_zero() {
    local value="$1"
    local param_name="$2"

    if [[ -z "$value" ]]; then
        print_error "$param_name cannot be empty"
        return 1
    fi

    if [[ ! "$value" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
        print_error "$param_name must be a valid number (e.g., '4', '2.5')"
        return 1
    fi

    if (($(echo "$value <= 0" | bc -l))); then
        print_error "$param_name must be greater than 0"
        return 1
    fi
}

test_kueue_on_remote() {
    if [[ -z "$WORKFLOW_NAME" ]]; then
        echo "WORKFLOW_NAME environment variable is not set. Please set it to the name of your workflow."
        exit 1
    fi

    # Only continue if no errors in check_remote_cluster_connection
    if ! check_remote_cluster_connection; then
        print_error "Remote cluster connection check failed. Aborting test."
        exit 1
    fi

    print_section "🧪 Testing Remote MultiKueue Setup"

    # Clean up any existing test jobs
    print_info "Cleaning up any existing test jobs..."
    kubectl delete jobs --all 2>/dev/null || true
    kubectl_cmd delete jobs --all 2>/dev/null || true

    print_section "Step 1: Submit Job to Remote Queue"

    # Create test job for remote queue using template
    local sample_job_file="kueue-sample-job.yaml"
    local test_job_name="remote-test-job"

    print_info "Creating remote test job from $sample_job_file template..."
    sed 's/kueue.x-k8s.io\/queue-name: job/kueue.x-k8s.io\/queue-name: '"$REMOTE"'-job-queue/g' "$(dirname "$0")/../etc/$sample_job_file" >"$test_job_name.yaml"

    print_info "Submitting job to remote queue..."
    run_cmd kubectl apply -f "$test_job_name.yaml"

    print_section "Step 2: Monitor Job Dispatch to Remote Cluster"

    print_info "Waiting for job to be dispatched to remote cluster..."
    local timeout=20
    local counter=0

    while [ $counter -lt $timeout ]; do
        # Check if job exists on remote cluster
        if kubectl_cmd get job "$test_job_name" 2>/dev/null | grep -q "$test_job_name"; then
            print_status "Job successfully dispatched to remote cluster!"
            break
        fi

        echo -n "."
        sleep 1
        counter=$((counter + 1))
    done

    if [ $counter -eq $timeout ]; then
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
    run_cmd kubectl_cmd get jobs -o wide

    print_info "Waiting for job to start on remote cluster..."
    run_cmd kubectl_cmd wait --for=condition=ready pod -l job-name="$test_job_name" --timeout=60s || true

    # Get pod name on remote cluster - try multiple approaches
    local remote_pod=""

    # First, try to find pod using job-name label (works when job exists)
    remote_pod=$(kubectl_cmd get pods -l job-name="$test_job_name" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

    # If no pod found with job-name label, try to find the newest busybox pod
    if [ -z "$remote_pod" ]; then
        print_info "Job-based pod lookup failed, searching for recent busybox pods on remote cluster..."
        remote_pod=$(kubectl_cmd get pods --sort-by=.metadata.creationTimestamp -o jsonpath='{range .items[*]}{.metadata.creationTimestamp}{" "}{.metadata.name}{" "}{.spec.containers[0].image}{"\n"}{end}' 2>/dev/null | grep "busybox" | tail -1 | awk '{print $2}' || echo "")

        if [ -z "$remote_pod" ]; then
            print_info "No busybox pod found, getting most recent pod on remote cluster..."
            remote_pod=$(kubectl_cmd get pods --sort-by=.metadata.creationTimestamp --no-headers -o custom-columns=":metadata.name" 2>/dev/null | tail -1 || echo "")
        fi
    fi

    if [ -n "$remote_pod" ]; then
        print_info "Found remote pod: $remote_pod"

        # Check if pod is already completed
        pod_status=$(kubectl_cmd get pod "$remote_pod" -o jsonpath='{.status.phase}' 2>/dev/null || echo "")

        print_section "--- Remote Job Logs ---"
        if [ "$pod_status" = "Succeeded" ] || [ "$pod_status" = "Failed" ]; then
            print_info "Pod already completed with status: $pod_status. Getting complete logs:"
            run_cmd kubectl_cmd logs "$remote_pod" || echo "No logs available"
        else
            print_info "Pod is running, streaming logs from remote cluster pod: $remote_pod"
            run_cmd kubectl_cmd logs "$remote_pod" -f --tail=100 || true
        fi
        print_section "--- End of Remote Job Logs ---"
        echo
    fi

    print_section "Step 4: Verify Job Completion"

    print_info "Checking for job completion on remote cluster..."
    local job_completed=false
    if kubectl_cmd get job "$test_job_name" >/dev/null 2>&1; then
        if run_cmd kubectl_cmd wait --for=condition=complete job/"$test_job_name" --timeout=120s; then
            print_status "Job completed successfully on remote cluster!"
            job_completed=true
        else
            print_error "Job did not complete within timeout"
            job_completed=false
        fi
    else
        print_info "Job not found (may have been cleaned up already). Checking pod status instead..."
        if [ -n "$remote_pod" ]; then
            local pod_status
            pod_status=$(kubectl_cmd get pod "$remote_pod" -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
            print_info "Pod status: $pod_status"
            if [ "$pod_status" = "Succeeded" ]; then
                print_status "Job completed successfully (determined from pod status)!"
                job_completed=true
            else
                print_error "Job did not complete successfully (pod status: $pod_status)"
                job_completed=false
            fi
        else
            print_error "No job or pod found to determine completion status"
            job_completed=false
        fi
    fi

    print_section "Step 5: Final Status Check"

    print_info "Final job status on MANAGER cluster:"
    run_cmd kubectl get jobs -o wide

    print_info "Final job status on REMOTE cluster:"
    run_cmd kubectl_cmd get jobs -o wide

    print_info "Workload status on manager cluster:"
    run_cmd kubectl get workloads -o wide

    print_info "Remote cluster events:"
    run_cmd kubectl_cmd get events --sort-by='.lastTimestamp' | tail -10

    print_section "Test Results"

    # Check if job completed successfully (using the kubectl wait result)
    if [ "$job_completed" = "true" ]; then
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
        kubectl delete -f "$test_job_name.yaml" >/dev/null 2>&1 || true # Remove from manager cluster (job manifest)
        kubectl_cmd delete jobs --all >/dev/null 2>&1 || true           # Remove from remote cluster
        rm -f "$test_job_name.yaml"

        exit 0
    else
        print_error "Remote MultiKueue test FAILED"
        print_info "Check the logs above for troubleshooting information"
        print_info "Job did not complete within the timeout period"
        exit 1
    fi
}

create_helper_pod() {
    local target_remote=$1
    local target_kubeconfig="$target_remote-kubeconfig.yaml"

    if kubectl --kubeconfig "$target_kubeconfig" get pod "$HELPER_POD" >/dev/null 2>&1; then
        return
    fi

    echo "Creating helper pod for $target_remote..."
    kubectl --kubeconfig "$target_kubeconfig" run "$HELPER_POD" --image=docker.io/library/ubuntu:24.04 --overrides='
    {
      "spec": {
        "containers": [
          {
            "name": "'$HELPER_POD'",
            "image": "docker.io/library/ubuntu:24.04",
            "volumeMounts": [
              {
                "name": "host-volume",
                "mountPath": "/var/reana"
              }
            ],
            "command": ["sleep", "infinity"]
          }
        ],
        "volumes": [
          {
            "name": "host-volume",
            "hostPath": {
              "path": "/var/reana",
              "type": "DirectoryOrCreate"
            }
          }
        ]
      }
    }'

    # Wait until pod is Running and Ready
    echo "Waiting for helper pod to be ready..."
    kubectl --kubeconfig "$target_kubeconfig" wait --for=condition=Ready pod/"$HELPER_POD" --timeout=30s
}

remove_helper_pod() {
    local target_remote=$1
    local target_kubeconfig="$target_remote-kubeconfig.yaml"

    echo "Cleaning up helper pod for $target_remote..."
    kubectl --kubeconfig "$target_kubeconfig" delete pod "$HELPER_POD" --force --grace-period 0

    # Wait until it’s gone
    kubectl --kubeconfig "$target_kubeconfig" wait --for=delete pod/"$HELPER_POD" --timeout=30s || true
}

ensure_reana_client_working() {
    if ! reana-client ping; then
        print_error "REANA client is not working. Please check your REANA access token and server URL."
        return 1
    fi
}

get_workflow_id() {
    local workflow_id
    workflow_id=$(reana-client list --size 1 --filter name="$WORKFLOW_NAME" --json --verbose | jq -r '.[].id')

    if [[ -z "$workflow_id" ]]; then
        print_error "No workflows found with name '$WORKFLOW_NAME'. Please run 'reana-client create -w $WORKFLOW_NAME' in your workflow directory first." >&2
        return 1
    fi

    echo "$workflow_id"
}

get_user_id() {
    echo "00000000-0000-0000-0000-000000000000"
}

get_workflow_dir() {
    local workflow_id

    if ! workflow_id=$(get_workflow_id); then
        return 1
    fi

    local user_id
    if ! user_id=$(get_user_id); then
        return 1
    fi

    echo "/var/reana/users/$user_id/workflows/$workflow_id"
}

ensure_workflow_name_set() {
    if [[ -z "$WORKFLOW_NAME" ]]; then
        print_error "WORKFLOW_NAME environment variable is not set. Please set it to the name of your workflow."
        exit 1
    fi
}

initialise_remote_workspace() {
    ensure_reana_client_working
    ensure_workflow_name_set

    local workflow_dir
    if ! workflow_dir=$(get_workflow_dir); then
        exit 1
    fi

    create_helper_pod "$REMOTE"

    echo "Creating secrets directory on remote..."
    kubectl_cmd exec -i -t "$HELPER_POD" -- /bin/bash -c "mkdir -p /etc/reana/secrets"

    # Copy all from local workspace to remote
    echo ""
    copy_between_pods "local:$workflow_dir" "$REMOTE:$workflow_dir" "true" "true" "Workflow files not found. Please run 'reana-client upload -w $WORKFLOW_NAME' in your workflow directory first."

    echo ""
    echo "Changing permissions..."
    kubectl_cmd exec -i -t "$HELPER_POD" -- /bin/bash -c "chmod -R 777 /var/reana/users"

    remove_helper_pod "$REMOTE"
}

get_local_pod() {
    # Find the pod with 'reana-server' in its name
    local local_pod
    local_pod=$(kubectl get pods --no-headers -o custom-columns=":metadata.name" | grep reana-server | head -n1)

    if [ -z "$local_pod" ]; then
        echo "Error: No reana-server pod found."
        exit 1
    fi

    echo "$local_pod"
}

copy_between_pods() {
    ensure_reana_client_working
    ensure_workflow_name_set

    local workflow_id
    if ! workflow_id=$(get_workflow_id); then
        exit 1
    fi

    local workflow_dir
    workflow_dir=$(get_workflow_dir)

    local source=$1
    local destination=$2
    local no_helper_pod=$3
    local no_base_path=$4
    local files_not_present_error_msg=$5

    # Parse source and destination
    local src_machine
    src_machine=$(echo "$source" | cut -d':' -f1)
    local src_path
    src_path=$(echo "$source" | cut -d':' -f2)
    local src_path_relative="$src_path"

    local dest_machine
    dest_machine=$(echo "$destination" | cut -d':' -f1)
    local dest_path
    dest_path=$(echo "$destination" | cut -d':' -f2)

    if [[ "$no_base_path" != "true" ]]; then
        src_path="$workflow_dir/$src_path"
        dest_path="$workflow_dir/$dest_path"
    fi

    if [[ "$src_machine" != "local" || "$dest_machine" != "local" ]]; then
        if [[ "$src_machine" != "local" ]]; then
            REMOTE="$src_machine"
        else
            REMOTE="$dest_machine"
        fi

        if ! check_remote_cluster_connection; then
            print_error "Remote cluster connection check failed. Aborting test."
            echo ""
            print_info "Run '$0 status' and check the connection status for '$REMOTE'."
            exit 1
        fi
    fi

    echo "Preparing to copy $src_machine:$src_path to $dest_machine:$dest_path"

    local src_pod
    if [[ "$src_machine" == "local" ]]; then
        src_pod=$(get_local_pod)
    else
        src_pod="$HELPER_POD"
    fi

    local dest_pod
    if [[ "$dest_machine" == "local" ]]; then
        dest_pod=$(get_local_pod)
    else
        dest_pod="$HELPER_POD"
    fi

    # Create helper pods if needed
    if [[ "$no_helper_pod" != "true" ]]; then
        if [[ "$src_machine" != "local" ]]; then
            create_helper_pod "$src_machine"
        fi
        if [[ "$dest_machine" != "local" ]]; then
            create_helper_pod "$dest_machine"
        fi
    fi

    # Wait for file to exist on src_machine
    while true; do
        if kubectl_with "$src_machine" exec "$src_pod" -- test -e "$src_path" 2>/dev/null; then
            print_info "Path '$src_path' found on $src_machine."
            break
        else
            if [[ -n "$files_not_present_error_msg" ]]; then
                print_info "Checking for files at '$src_machine:$src_pod:$src_path'..."
                print_error "$files_not_present_error_msg"
                return 1
            fi

            print_info "Waiting for path at '$src_machine:$src_pod:$src_path'..."
            sleep 2
        fi
    done

    echo ""

    # Copy from the source to tmp on the local machine.
    local tmp="/tmp/reana/workflows/$workflow_id"
    local hop_path="$tmp/$src_path_relative"

    local hop_path_dir
    hop_path_dir=$(dirname "$hop_path")
    echo "Ensuring tmp directory $hop_path_dir exists..."
    mkdir -p "$hop_path_dir"

    echo "Copying from $src_machine:$src_pod:$src_path to $hop_path..."
    kubectl_with "$src_machine" cp "$src_pod:$src_path" "$hop_path"

    # Now we have the source file in tmp and we need to copy it to the pod
    echo ""

    # Create destination directory if needed
    echo "Ensuring destination directory $dest_machine:$dest_pod:$dest_path exists..."
    local dest_dir
    dest_dir=$(dirname "$dest_path")
    kubectl_with "$dest_machine" exec -i -t "$dest_pod" -- /bin/bash -c "mkdir -p $dest_dir"

    # Copy file
    echo "Copying from $hop_path to $dest_machine:$dest_path..."
    kubectl_with "$dest_machine" cp "$hop_path" "$dest_pod:$dest_path"
    kubectl_with "$dest_machine" exec -i -t "$dest_pod" -- /bin/bash -c "chmod -R 777 $workflow_dir"

    echo ""

    # Clean up helper pods
    if [[ "$no_helper_pod" != "true" ]]; then
        if [[ "$src_machine" != "local" ]]; then
            remove_helper_pod "$src_machine"
        fi
        if [[ "$dest_machine" != "local" ]]; then
            remove_helper_pod "$dest_machine"
        fi
    fi
}

# Help
usage() {
    local command="$1"

    echo "A helper script to manage the optional Kueue workload system alongside REANA deployments."
    echo ""
    echo "IMPORTANT:"
    echo "This script is meant for development purposes only and should not be used in production."
    echo ""

    case "$command" in
    install)
        echo "USAGE:"
        echo "  $0 install [--help]"
        echo ""
        echo "DESCRIPTION:"
        echo "  Install Kueue via Helm"
        echo ""
        echo "OPTIONS:"
        echo "  --help, -h           : Display this help message"
        ;;
    connect)
        echo "USAGE:"
        echo "  $0 connect --remote <remote> [--help]"
        echo ""
        echo "DESCRIPTION:"
        echo "  Connect the manager to a remote cluster"
        echo ""
        echo "OPTIONS:"
        echo "  --help, -h           : Display this help message"
        ;;
    monitor)
        echo "USAGE:"
        echo "  $0 monitor [OPTIONS] [--help]"
        echo ""
        echo "DESCRIPTION:"
        echo "  Monitor active Kueue workloads and jobs"
        echo ""
        echo "OPTIONS:"
        echo "  --refresh-interval   : Set monitor refresh interval in seconds (default: ${MONITOR_REFRESH_INTERVAL_SECS}s)"
        echo "  --help, -h           : Display this help message"
        ;;
    remove)
        echo "USAGE:"
        echo "  $0 remove [OPTIONS] [--help]"
        echo ""
        echo "DESCRIPTION:"
        echo "  Remove Kueue components"
        echo ""
        echo "OPTIONS:"
        echo "  --all                : Remove all Kueue components (default if no specific flags)"
        echo "  --kueue              : Remove Kueue installation (Helm chart) only"
        echo "  --resources          : Remove Kueue resources (queues, flavors) only"
        echo "  --workloads          : Remove active workloads only"
        echo "  --help, -h           : Display this help message"
        ;;
    status)
        echo "USAGE:"
        echo "  $0 status [--help]"
        echo ""
        echo "DESCRIPTION:"
        echo "  Check Kueue installation, configuration, and status of resources and remote workers"
        echo ""
        echo "OPTIONS:"
        echo "  --help, -h           : Display this help message"
        ;;
    test)
        echo "USAGE:"
        echo "  $0 test [OPTIONS] [--help]"
        echo ""
        echo "DESCRIPTION:"
        echo "  Test the remote cluster connection by launching and monitoring a sample job"
        echo ""
        echo "OPTIONS:"
        echo "  --help, -h           : Display this help message"
        ;;
    initialise-workspace)
        echo "USAGE:"
        echo "  $0 initialise-workspace --remote <remote> [--help]"
        echo ""
        echo "DESCRIPTION:"
        echo "  Initialise a REANA workspace on a remote cluster."
        echo "  This is necessary before running any workloads on the remote cluster and"
        echo "  should be run after 'reana-client create' and 'reana-client upload'."
        echo "  It copies all workflow files to the remote cluster."
        echo ""
        echo "OPTIONS:"
        echo "  --help, -h           : Display this help message"
        ;;
    copy)
        echo "USAGE:"
        echo "  $0 copy <src>:<src_path> <dest>:<dest_path> [--help]"
        echo ""
        echo "DESCRIPTION:"
        echo "  Copy files or directories between pods on different clusters."
        echo "  The src and dest can be 'local' or a remote cluster name."
        echo "  The src and dest paths are relative to the workflow workspace which"
        echo "  is inferred from the WORKFLOW_NAME environment variable."
        echo "  The workflow used is the latest one called \$WORKFLOW_NAME."
        echo ""
        echo "OPTIONS:"
        echo "  --help, -h           : Display this help message"
        ;;
    *)
        echo "USAGE:"
        echo "  $0 <command> [options]"
        echo ""
        echo "COMMANDS:"
        echo "  install                         : Install Kueue via Helm"
        echo "  connect                         : Connect the manager to a remote cluster"
        echo "  monitor                         : Monitor active Kueue workloads and jobs"
        echo "  remove                          : Remove Kueue components"
        echo "  status                          : Check Kueue installation status"
        echo "  test                            : Launch and monitor a sample job as it is created and dispatched to a remote cluster"
        echo "  initialise-workspace            : Initialise a REANA workspace on a remote cluster"
        echo "  copy <src>:<path> <dest>:<path> : Copy files or directories between pods on different clusters"
        echo ""
        echo "GLOBAL OPTIONS:"
        echo "  --local           : Operate on local cluster (default)"
        echo "  --remote          : Operate on remote cluster"
        echo "  --help, -h        : Show help for command or general usage"
        echo ""
        echo "EXAMPLES:"
        echo "  $0 install"
        echo "  $0 install --remote datacenter1"
        echo "  $0 connect --remote datacenter2"
        echo "  $0 disconnect --remote datacenter2"
        echo "  $0 monitor --refresh-interval 5"
        echo "  $0 remove --kueue --resources"
        echo "  $0 remove --workloads --remote"
        echo "  $0 test --remote datacenter1"
        echo "  $0 initialise-workspace --remote datacenter1"
        echo "  $0 copy local:code/my_code.py datacenter1:code/my_code.py"
        echo "  $0 copy datacenter1:all_results datacenter2:local_results_folder"
        echo ""
        echo "PREREQUISITES:"
        echo "  - kubectl configured and connected to your cluster"
        echo "  - Helm 3.x installed"
        echo "  - Cluster admin permissions"
        echo "  - Internet access (for downloading Helm chart)"
        ;;
    esac
}

# Parse command and options
if [[ $# -eq 0 ]]; then
    usage
    exit 1
fi

COMMAND="$1"
ARG1="$2"
ARG2="$3"
shift

VALIDATION_ERRORS=0
HELP_REQUESTED=false

# Parse options based on command
while [[ $# -gt 0 ]]; do
    case $1 in
    --local)
        CLUSTER_MODE="local"
        ;;
    --remote)
        # Check if any remotes are available (REMOTES is not empty)
        if [[ -z "$REMOTES" ]]; then
            print_error "No remotes found. Please create *-kubeconfig.yaml and *-resources.yaml files in your current directory first to define your remotes."
            exit 1
        fi

        REMOTE="$2"

        # Require a name to be specified with --remote
        if [[ -z "$REMOTE" ]]; then
            print_error "Please specify a remote name with --remote."
            if [[ -n "${REMOTES:-}" ]]; then
                print_info "Available remotes: $REMOTES"
            fi
            exit 1
        fi

        # Check if the name specified with --remote exists in the list of REMOTES
        if [[ ! "$REMOTES" =~ (^|,)${REMOTE}(,|$) ]]; then
            print_error "Remote '$REMOTE' not found in list of available remotes: $REMOTES"
            exit 1
        fi

        # Set REMOTE_KUBECONFIG to the argument passed to --remote
        REMOTE_KUBECONFIG="$REMOTE-kubeconfig.yaml"
        shift

        print_info "Executing with Kubeconfig: $REMOTE_KUBECONFIG"
        echo ""

        CLUSTER_MODE="remote"
        ;;
    --all)
        if [[ "$COMMAND" != "remove" ]]; then
            print_error "--all is only valid for the 'remove' command"
            VALIDATION_ERRORS=1
        else
            REMOVE_ALL=true
        fi
        ;;
    --workloads)
        if [[ "$COMMAND" != "remove" ]]; then
            print_error "--workloads is only valid for the 'remove' command"
            VALIDATION_ERRORS=1
        else
            REMOVE_WORKLOADS=true
        fi
        ;;
    --resources)
        if [[ "$COMMAND" != "remove" ]]; then
            print_error "--resources is only valid for the 'remove' command"
            VALIDATION_ERRORS=1
        else
            REMOVE_RESOURCES=true
        fi
        ;;
    --kueue)
        if [[ "$COMMAND" != "remove" ]]; then
            print_error "--kueue is only valid for the 'remove' command"
            VALIDATION_ERRORS=1
        else
            REMOVE_KUEUE=true
        fi
        ;;
    --refresh-interval)
        if [[ "$COMMAND" != "monitor" ]]; then
            print_error "--refresh-interval is only valid for the 'monitor' command"
            VALIDATION_ERRORS=1
        elif [[ -z "$2" ]]; then
            print_error "--refresh-interval requires a value"
            VALIDATION_ERRORS=1
        else
            if validate_num_greater_than_zero "$2" "refresh interval"; then
                MONITOR_REFRESH_INTERVAL_SECS="$2"
            else
                VALIDATION_ERRORS=1
            fi
            shift
        fi
        ;;
    --help | -h)
        HELP_REQUESTED=true
        ;;
    *)
        # Check if option starts with --. If so, it's an unknown option.
        if [[ "$1" == --* ]]; then
            print_error "Unknown option: $1"
            echo "Use '--help' to see available options for the '$COMMAND' command"
            exit 1
        fi
        ;;
    esac
    shift
done

# Handle help request
if [[ "$HELP_REQUESTED" = true ]]; then
    usage "$COMMAND"
    exit 0
fi

# Exit if validation errors occurred
if [[ $VALIDATION_ERRORS -eq 1 ]]; then
    echo ""
    echo "Please fix the validation errors above and try again."
    echo "Use '$0 $COMMAND --help' to see available options."
    exit 1
fi

# Execute command
case $COMMAND in
install)
    install_kueue
    ;;
connect)
    connect_node
    ;;
disconnect)
    disconnect_node
    ;;
monitor)
    monitor_kueue
    ;;
remove)
    handle_remove
    ;;
status)
    if [[ "$CLUSTER_MODE" = "connection" ]]; then
        if check_remote_cluster_connection; then
            echo ""
            print_status "Remote MultiKueue configuration verified."
        else
            echo ""
            print_error "There are issues with the remote MultiKueue setup."
        fi
    else
        show_kueue_status
    fi
    ;;
test)
    if [[ "$CLUSTER_MODE" != "remote" ]]; then
        print_error "Please specify a remote cluster to test with --remote."
        exit 1
    fi

    test_kueue_on_remote
    ;;
initialise-workspace)
    if [[ "$CLUSTER_MODE" != "remote" ]]; then
        print_error "Please specify a remote cluster to test with --remote."
        exit 1
    fi

    if ! check_remote_cluster_connection; then
        print_error "Remote cluster connection check failed. Aborting test."
        echo ""
        print_info "Run '$0 status' and check the connection status for '$REMOTE'."
        exit 1
    fi

    initialise_remote_workspace
    ;;
copy)
    # Ensure arguments are provided
    if [[ -z "$ARG1" || -z "$ARG2" ]]; then
        print_error "Please provide source and destination arguments. For usage, run '$0 copy --help'."
        exit 1
    fi

    copy_between_pods "$ARG1" "$ARG2"
    ;;
help | h | --help | -h)
    usage
    ;;
*)
    print_error "Unknown command: $COMMAND"
    echo ""
    usage
    exit 1
    ;;
esac
