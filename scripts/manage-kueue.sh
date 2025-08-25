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

find_kubeconfigs() {
    local kubeconfigs
    kubeconfigs=$(find "$PWD" -maxdepth 1 -name '*.kubeconfig' 2>/dev/null | sed 's/\.kubeconfig$//' | xargs -n1 basename | paste -sd ',' -)
    echo "$kubeconfigs"
}

find_resources_files() {
    local resources_files
    resources_files=$(find "$PWD" -maxdepth 1 -name '*-resources.yaml' 2>/dev/null)
    echo "$resources_files"
}

# Check the current directory for any *.kubeconfig files and build a list of names (without the file extension)
REMOTES=$(find_kubeconfigs)

# Default config for monitor command
MONITOR_REFRESH_INTERVAL_SECS=3

# Default config for remove command
REMOVE_ALL=false
REMOVE_WORKLOADS=false
REMOVE_RESOURCES=false
REMOVE_KUEUE=false
REMOVE_CONNECTION=false

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

create_cluster() {
    # Configuration
    local colima_profile="multikueue-manager"
    local manager_cluster_name="manager"
    local manager_cluster_config="../etc/manager-config.yaml"

    # Check for existence of manager-config.yaml
    if [ ! -f "$manager_cluster_config" ]; then
        print_error "$manager_cluster_config file not found. Please pull it from the GitHub repo."
        exit 1
    fi

    # Check prerequisites
    echo -e "${BLUE}📋 Checking prerequisites...${NC}"

    # Check if Homebrew is installed
    if ! command -v brew &>/dev/null; then
        print_error "Homebrew is not installed. Please install it first: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
    print_status "Homebrew is installed"

    # Install required tools
    echo -e "${BLUE}🔧 Installing required tools...${NC}"

    tools=("colima" "kubectl" "kind" "helm")
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &>/dev/null; then
            echo "Installing $tool..."
            run_cmd brew install "$tool"
            print_status "$tool installed"
        else
            print_status "$tool already installed"
        fi
    done

    # Delete any existing manager Colima profile for a clean start
    echo -e "${BLUE}🗑️  Deleting any existing manager Colima profile...${NC}"
    run_cmd colima delete --profile $colima_profile --force 2>/dev/null || true
    print_status "Existing manager Colima profile deleted"

    # Start Colima with adequate resources and network access
    echo -e "${BLUE}🐋 Starting Colima with profile: $colima_profile${NC}"
    run_cmd colima start --profile $colima_profile \
        --cpu 4 \
        --memory 8 \
        --disk 50 \
        --network-address \
        --kubernetes=false \
        --runtime docker

    print_status "Colima started with profile: $colima_profile"

    # Wait for Colima to be ready
    echo "Waiting for Colima to be ready..."
    sleep 10

    # Create manager cluster (no custom network needed in separate VM setup)
    echo -e "${BLUE}🏗️  Creating manager cluster: $manager_cluster_name${NC}"
    run_cmd kind create cluster --config "$manager_cluster_config"

    print_status "Manager cluster '$manager_cluster_name' created"

    # Verify cluster
    echo -e "${BLUE}🔍 Verifying manager cluster context...${NC}"
    run_cmd kubectl config use-context kind-$manager_cluster_name
    run_cmd kubectl get nodes
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

apply_resource_files() {
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

    # Get number of resources
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

    if [[ "$CLUSTER_MODE" = "local" ]]; then
        cat <<EOF | kubectl_cmd apply -f -
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: LocalQueue
metadata:
  namespace: "default"
  name: "batch"
spec:
  clusterQueue: "batch"
EOF

        print_info "Applying batch ClusterQueue..."
        cat <<EOF | kubectl_cmd apply -f -
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: ClusterQueue
metadata:
  name: "batch"
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

    print_info "Applying Job LocalQueue..."
    cat <<EOF | kubectl_cmd apply -f -
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: LocalQueue
metadata:
  namespace: "default"
  name: "job"
spec:
  clusterQueue: "job"
EOF

    print_info "Applying job ClusterQueue..."

    if [[ "$CLUSTER_MODE" = "local" ]]; then
        # Manager
        cat <<EOF | kubectl_cmd apply -f -
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: ClusterQueue
metadata:
  name: "job"
spec:
  namespaceSelector: {}
  resourceGroups:
  - coveredResources: ["cpu", "memory"]
    flavors:
$(echo -e "$job_cluster_queue_flavors")
  admissionChecks:
  - job
EOF
    else
        # Remote
        cat <<EOF | kubectl_cmd apply -f -
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: ClusterQueue
metadata:
  name: "job"
spec:
  namespaceSelector: {}
  resourceGroups:
  - coveredResources: ["cpu", "memory"]
    flavors:
$(echo -e "$job_cluster_queue_flavors")
EOF
    fi

    # Only apply admission checks if in local mode
    if [[ "$CLUSTER_MODE" = "local" ]]; then
        print_info "Applying AdmissionCheck..."
        cat <<EOF | kubectl_cmd apply -f -
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: AdmissionCheck
metadata:
  name: job
spec:
  controllerName: kueue.x-k8s.io/multikueue
  parameters:
    apiGroup: kueue.x-k8s.io
    kind: MultiKueueConfig
    name: multikueue-config
EOF
    fi
}

configure_manager() {
    # Check if kueue is installed
    if ! check_kueue_installed; then
        print_error "Kueue is not installed. Please run the 'install' command first."
        exit 1
    fi

    # Check if there are remotes available
    if [[ -z "$REMOTES" ]]; then
        print_error "No remotes found. Please create *.kubeconfig and *-resources.yaml files first to define your remotes."
        exit 1
    fi

    print_status "Manager is ready to be configured with a remote. Use the --remote flag to configure a remote and connect it to the manager."
}

configure_remote() {
    if ! check_kueue_installed; then
        print_error "Kueue is not installed. Please run the 'install --remote $REMOTE' command first."
        return 1
    fi

    local resources_file="$REMOTE-resources.yaml"

    if [ ! -f "$resources_file" ]; then
        print_error "Resources file '$resources_file' not found. Please create it first."
        return 1
    fi

    # Run in manager first
    print_section "📄 Applying resources manifest '$resources_file' to manager..."
    local temp_cluster_mode="$CLUSTER_MODE"
    CLUSTER_MODE="local"
    apply_resource_files
    echo ""

    # Then run in remote
    print_section "📄 Applying resources manifest '$resources_file' to $REMOTE..."
    CLUSTER_MODE="remote"
    apply_resource_files

    # Copy secrets to remote
    print_section "📄 Copying secret to remote..."
    local secret_name="reana-secretsstore-00000000-0000-0000-0000-000000000000"
    # Check if secret already exists
    if kubectl_cmd get secret "$secret_name" &>/dev/null; then
        print_info "Secret already exists"
    else
        kubectl get secret "$secret_name" -o yaml | kubectl_cmd apply -f -
    fi
    CLUSTER_MODE="$temp_cluster_mode"

    sleep 1
    echo ""
    print_status "Resources applied"
    echo ""

    if verify_kueue_resources "require-resources"; then
        connect_remote_cluster
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
    local should_remove_connection=$REMOVE_CONNECTION

    # If --all is specified, remove everything
    if [ "$REMOVE_ALL" = "true" ]; then
        should_remove_workloads=true
        should_remove_resources=true
        should_remove_kueue=true
        should_remove_connection=true
    fi

    # If no specific flags are set, default to the original behavior (remove all)
    if [ "$REMOVE_WORKLOADS" = "false" ] && [ "$REMOVE_RESOURCES" = "false" ] &&
        [ "$REMOVE_KUEUE" = "false" ] &&
        [ "$REMOVE_ALL" = "false" ] &&
        [ "$REMOVE_CONNECTION" = "false" ]; then
        should_remove_workloads=true
        should_remove_resources=true
        should_remove_kueue=true
        should_remove_connection=true
    fi

    # Show what will be removed
    print_info "Components to be removed:"
    [ "$should_remove_workloads" = "true" ] && echo -e "${BLUE}  • Workloads${NC}"
    [ "$should_remove_resources" = "true" ] && echo -e "${BLUE}  • Kueue resources (queues, flavors)${NC}"
    [ "$should_remove_kueue" = "true" ] && echo -e "${BLUE}  • Kueue installation (Helm chart)${NC}"
    [ "$should_remove_connection" = "true" ] && echo -e "${BLUE}  • Remove cluster connection${NC}"
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

    # Remove cluster connection if requested
    if [ "$should_remove_connection" = "true" ]; then
        if [ "$CLUSTER_MODE" = "remote" ]; then
            disconnect_remote_cluster
        else
            print_warning "Cannot remove cluster connection without specifying a --remote cluster."
        fi
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
    local will_remove_connection=$REMOVE_CONNECTION

    if [ "$REMOVE_ALL" = "true" ]; then
        will_remove_resources=true
        will_remove_kueue=true
        will_remove_workloads=true
        will_remove_connection=true
    fi

    # If no specific flags, default to all
    if [ "$REMOVE_WORKLOADS" = "false" ] && [ "$REMOVE_RESOURCES" = "false" ] &&
        [ "$REMOVE_KUEUE" = "false" ] &&
        [ "$REMOVE_ALL" = "false" ] &&
        [ "$REMOVE_CONNECTION" = "false" ]; then
        will_remove_resources=true
        will_remove_kueue=true
        will_remove_workloads=true
        will_remove_connection=true
    fi

    # Build component list
    [ "$will_remove_resources" = "true" ] && components="${components}\n  • Kueue resources (queues, flavors)"
    [ "$will_remove_kueue" = "true" ] && components="${components}\n  • Kueue installation (Helm chart and namespace)"
    [ "$will_remove_workloads" = "true" ] && components="${components}\n  • Workloads"

    if [ "$CLUSTER_MODE" = "remote" ]; then
        [ "$will_remove_connection" = "true" ] && components="${components}\n  • Remote cluster connection ($REMOTE)"
    fi

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

    local secret_name="$REMOTE-secret"

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

    # Create MultiKueueCluster
    print_info "Creating MultiKueueCluster..."
    run_cmd kubectl apply -f - <<EOF
---
# MultiKueueCluster for remote worker
apiVersion: kueue.x-k8s.io/v1beta1
kind: MultiKueueCluster
metadata:
  name: $REMOTE-multikueue-cluster
  namespace: kueue-system
spec:
  kubeConfig:
    locationType: Secret
    location: $secret_name
EOF

    if kubectl get multikueueconfig multikueue-config -n kueue-system >/dev/null 2>&1; then
        # Check if remote already exists in multikueueconfig
        if kubectl get multikueueconfig multikueue-config -n kueue-system -o jsonpath='{.spec.clusters}' | grep -q "$REMOTE-multikueue-cluster"; then
            print_info "Remote $REMOTE already exists in MultiKueueConfig. Skipping..."
        else
            print_info "MultiKueueConfig already exists. Patching..."
            # multikueueconfig exists: append new cluster
            kubectl patch multikueueconfig multikueue-config \
                -n kueue-system \
                --type='json' \
                -p "[{\"op\": \"add\", \"path\": \"/spec/clusters/-\", \"value\": \"${REMOTE}-multikueue-cluster\"}]"
        fi
    else
        # multikueueconfig doesn't exist: create fresh config
        print_info "Creating MultiKueueConfig..."
        kubectl apply -f - <<EOF
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: MultiKueueConfig
metadata:
  name: multikueue-config
  namespace: kueue-system
spec:
  clusters:
  - ${REMOTE}-multikueue-cluster
EOF
    fi

    print_status "MultiKueueCluster connection created using kubeconfig: $REMOTE_KUBECONFIG"
}

disconnect_remote_cluster() {
    print_section "🔌 Disconnecting Remote Cluster..."

    # Temporarily unset REMOTE_KUBECONFIG while we delete resources from the manager
    local temp_kubeconfig="$REMOTE_KUBECONFIG"
    REMOTE_KUBECONFIG=""

    # Remove MultiKueue resources
    print_info "Removing MultiKueue resources..."
    force_delete_resources "multikueuecluster" "$REMOTE-multikueue-cluster" "-n kueue-system"
    force_delete_resources "secret" "$REMOTE-secret" "-n kueue-system"

    # Amend MultiKueueConfig to remove reference to multikueue cluster
    if kubectl get multikueueconfig multikueue-config -n kueue-system >/dev/null 2>&1; then
        print_info "Patching MultiKueueConfig to remove reference to $REMOTE-multikueue-cluster..."
        kubectl patch multikueueconfig multikueue-config \
            -n kueue-system \
            --type='json' \
            -p "[{\"op\": \"remove\", \"path\": \"/spec/clusters\", \"value\": [\"${REMOTE}-multikueue-cluster\"]}]" || true
    fi

    # Restore REMOTE_KUBECONFIG
    REMOTE_KUBECONFIG="$temp_kubeconfig"

    print_status "Remote cluster disconnected successfully"
}

# Status check for Kueue
status_kueue() {
    print_section "📊 Kueue Status Report$(if [[ "$CLUSTER_MODE" = "remote" ]]; then echo " ($REMOTE)"; fi)"
    echo ""

    # Check if Kueue is enabled in values.yaml (local mode only)
    local kueue_enabled_in_config=false
    if [[ "$CLUSTER_MODE" = "local" ]]; then
        print_section "⚙️  Configuration Check"
        local values_file
        values_file="$(dirname "$0")/../helm/reana/values.yaml"

        if [[ -f "$values_file" ]]; then
            if grep -q "kueue:" "$values_file" && grep -A1 "kueue:" "$values_file" | grep -q "enabled: true"; then
                print_status "Kueue is enabled in values.yaml"
                kueue_enabled_in_config=true
            else
                print_warning "Kueue is not enabled in values.yaml"
            fi
        else
            print_error "values.yaml file not found at $values_file"
        fi
        echo ""
    fi

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
    print_section "🎨 ResourceFlavors"
    local rf_count
    rf_count=$(kubectl_cmd get resourceflavors --no-headers 2>/dev/null | wc -l)

    if [[ "$rf_count" -gt 0 ]]; then
        print_info "Found $rf_count ResourceFlavor(s):"
        kubectl_cmd get resourceflavors --no-headers 2>/dev/null | while read -r name age; do
            echo -e "${WHITE}   • $name (age: $age)${NC}"
        done
    else
        print_warning "No ResourceFlavors found"
    fi
    echo ""

    # Check LocalQueues
    print_section "🏪 LocalQueues"
    local lq_count
    lq_count=$(kubectl_cmd get localqueues -A --no-headers 2>/dev/null | wc -l)

    if [[ "$lq_count" -gt 0 ]]; then
        print_info "Found $lq_count LocalQueue(s):"
        kubectl_cmd get localqueues -A -o custom-columns="NAMESPACE:.metadata.namespace,NAME:.metadata.name,CLUSTERQUEUE:.spec.clusterQueue,PENDING:.status.pendingWorkloads,ADMITTED:.status.admittedWorkloads" --no-headers 2>/dev/null | while read -r line; do
            echo -e "${WHITE}   • $line${NC}"
        done
    else
        print_warning "No LocalQueues found"
    fi
    echo ""

    # Check ClusterQueues
    print_section "🏢 ClusterQueues"
    local cq_count
    cq_count=$(kubectl_cmd get clusterqueues --no-headers 2>/dev/null | wc -l)

    if [[ "$cq_count" -gt 0 ]]; then
        print_info "Found $cq_count ClusterQueue(s):"
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
    if [[ "$CLUSTER_MODE" = "local" ]]; then
        print_section "🔗 Available Remotes"
        if [[ -n "$REMOTES" ]]; then
            # Get list of fully configured remotes
            local configured_remotes=()
            while read -r remote; do
                local has_config=false
                local has_cluster=false
                local has_secret=false

                # Check for multikueueconfig
                if kubectl get multikueueconfigs "multikueue-config" -n kueue-system >/dev/null 2>&1; then
                    has_config=true
                fi

                # Check for multikueuecluster
                if kubectl get multikueueclusters "$remote-multikueue-cluster" -n kueue-system >/dev/null 2>&1; then
                    has_cluster=true
                fi

                # Check for secret
                if kubectl get secret "$remote-secret" -n kueue-system >/dev/null 2>&1; then
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
                if kubectl --kubeconfig="$remote.kubeconfig" get namespaces >/dev/null 2>&1; then
                    if $is_configured; then
                        echo -e "${GREEN}   ✓ $remote (configured)${NC}"
                    else
                        # Check if Kueue is installed
                        local temp_cluster_mode="$CLUSTER_MODE"
                        local temp_remote_kubeconfig="$REMOTE_KUBECONFIG"
                        CLUSTER_MODE="remote"
                        REMOTE_KUBECONFIG="$remote.kubeconfig"
                        if check_kueue_installed "quiet"; then
                            echo -e "${WHITE}   • $remote (reachable, not connected)${NC}"
                        else
                            echo -e "${YELLOW}   • $remote (reachable, Kueue not installed)${NC}"
                            some_kueue_not_installed=true
                        fi
                        CLUSTER_MODE="$temp_cluster_mode"
                        REMOTE_KUBECONFIG="$temp_remote_kubeconfig"
                    fi
                else
                    echo -e "${RED}   ✗ $remote (unreachable)${NC}"
                    some_unreachable=true
                fi
            done <<<"$(echo "$REMOTES" | tr ',' '\n')"

            # Summary messages
            if $some_unreachable; then
                print_warning "Some remotes are unreachable. Please make sure the kubeconfigs are correct."
            elif $some_kueue_not_installed; then
                print_warning "Some remotes do not have Kueue installed. Please install Kueue before connecting them."
            fi
        else
            print_info "No remotes found"
        fi
        echo ""

        print_section "📋 Detected Kubeconfigs"
        local kubeconfigs
        kubeconfigs=$(find_kubeconfigs)
        if [[ -n "$kubeconfigs" ]]; then
            echo "$kubeconfigs" | tr ',' '\n' | while read -r kubeconfig; do
                echo -e "${WHITE}   • $kubeconfig${NC}"
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
                echo -e "${WHITE}   • $resources_file${NC}"

                local count
                count=$(yq e '.resources | length' "$resources_file")

                for ((i = 0; i < count; i++)); do
                    local name cpu memory

                    name=$(yq e ".resources[$i].name" "$resources_file")
                    cpu=$(yq e ".resources[$i].cpu" "$resources_file")
                    memory=$(yq e ".resources[$i].memory" "$resources_file")

                    echo -e "${BLUE}     - $name: cpu=$cpu, memory=$memory${NC}"
                done
            done
        else
            print_info "No resource manifests found"
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

            if [[ "$wl_count" -gt 0 ]]; then
                print_info "Currently processing $wl_count workload(s)"
            else
                print_info "No active workloads"
            fi
        else
            print_warning "Configuration still required (queues, flavors, etc)"
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

    local secret_name="$REMOTE-secret"
    local cluster_name="$REMOTE-multikueue-cluster"
    local config_name="$REMOTE-multikueue-config"

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
    if ! kubectl get multikueuecluster "$cluster_name" >/dev/null 2>&1; then
        print_error "MultiKueueCluster '$cluster_name' not found."
        errors_present=true
    else
        print_status "MultiKueueCluster '$cluster_name' exists."
    fi

    # Verify MultiKueueConfig
    print_info "Checking MultiKueueConfig..."
    if ! kubectl get multikueueconfig "$config_name" -n kueue-system >/dev/null 2>&1; then
        print_error "MultiKueueConfig '$config_name' not found in namespace kueue-system."
        errors_present=true
    else
        print_status "MultiKueueConfig '$config_name' exists in namespace kueue-system."
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

# Validation functions (kept same as original)
validate_cpu() {
    local value="$1"
    local param_name="$2"

    validate_num_greater_than_zero "$value" "$param_name"

    if (($(echo "$value > 1000" | bc -l))); then
        print_warning "$param_name value ($value) seems unusually high"
    fi

    return 0
}

validate_memory() {
    local value="$1"
    local param_name="$2"

    if [[ -z "$value" ]]; then
        print_error "$param_name cannot be empty"
        return 1
    fi

    if [[ ! "$value" =~ ^[0-9]+(\.[0-9]+)?(E|P|T|G|M|K|Ei|Pi|Ti|Gi|Mi|Ki)?$ ]]; then
        print_error "$param_name must be in valid Kubernetes format"
        echo "  Valid examples: '1Gi', '512Mi', '2Ti', '1000000000' (bytes), '129e6' (bytes)"
        echo "  Supported units: E, P, T, G, M, K | OR | Ei, Pi, Ti, Gi, Mi, Ki"
        return 1
    fi

    if [[ "$value" =~ ^([0-9]+(\.[0-9]+)?)([A-Za-z]*)$ ]]; then
        local numeric_part="${BASH_REMATCH[1]}"
        local unit="${BASH_REMATCH[3]}"

        if (($(echo "$numeric_part <= 0" | bc -l))); then
            print_error "$param_name must be greater than 0"
            return 1
        fi

        case "$unit" in
        "Ei" | "E") multiplier="1000000000000000000" ;;
        "Pi" | "P") multiplier="1000000000000000" ;;
        "Ti" | "T") multiplier="1000000000000" ;;
        "Gi" | "G") multiplier="1000000000" ;;
        "Mi" | "M") multiplier="1000000" ;;
        "Ki" | "K") multiplier="1000" ;;
        "") multiplier="1" ;;
        *) multiplier="1" ;;
        esac

        local bytes
        bytes=$(echo "$numeric_part * $multiplier" | bc -l)
        local ten_ti
        ten_ti=$(echo "10 * 1000000000000" | bc -l)
        if (($(echo "$bytes > $ten_ti" | bc -l))); then
            print_warning "$param_name value ($value) seems unusually high"
        fi
    fi

    return 0
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
    configure)
        echo "USAGE:"
        echo "  $0 configure [OPTIONS] [--help]"
        echo ""
        echo "DESCRIPTION:"
        echo "  Configure queues, quotas, and flavors"
        echo ""
        echo "OPTIONS:"
        echo "  --help, -h           : Display this help message"
        echo ""
        echo "RESOURCE QUOTA GUIDELINES:"
        echo "  Resource quotas represent the TOTAL resources available across your entire cluster"
        echo "  for each queue type, not per-node or per-pod limits."
        echo ""
        echo "  Example:"
        echo "    - Cluster: 5 nodes × 8 CPUs each = 40 total CPUs"
        echo "    - Allocation: 3 CPUs for batch jobs, 30 CPUs for regular jobs, (7 reserved for system)"
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
        echo "  --connection         : Remove remote cluster connection only (requires the --remote flag to be set)"
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
    *)
        echo "USAGE:"
        echo "  $0 <command> [options]"
        echo ""
        echo "COMMANDS:"
        echo "  install              : Install Kueue via Helm"
        echo "  configure            : Configure queues, quotas, and flavors"
        echo "  monitor              : Monitor active Kueue workloads and jobs"
        echo "  remove               : Remove Kueue components"
        echo "  status               : Check Kueue installation status"
        echo "  test                 : Launch and monitor a sample job as it is created and dispatched to a remote cluster"
        echo ""
        echo "GLOBAL OPTIONS:"
        echo "  --local              : Operate on local cluster (default)"
        echo "  --remote             : Operate on remote cluster"
        echo "  --help, -h           : Show help for command or general usage"
        echo ""
        echo "EXAMPLES:"
        echo "  $0 install"
        echo "  $0 install --remote"
        echo "  $0 install --remote datacenter1"
        echo "  $0 configure --batch-cpu 4 --job-memory 8Gi"
        echo "  $0 configure --remote datacenter2"
        echo "  $0 monitor --refresh-interval 5"
        echo "  $0 remove --kueue --resources"
        echo "  $0 remove --workloads --remote"
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
        if [ "$COMMAND" = "create-manager-cluster" ]; then
            print_error "--remote is not valid for the '$COMMAND' command"
            VALIDATION_ERRORS=1
        fi

        # Check if any remotes are available (REMOTES is not empty)
        if [[ -z "$REMOTES" ]]; then
            print_error "No remotes found. Please create *.kubeconfig and *-resources.yaml files in your current directory first to define your remotes."
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
        REMOTE_KUBECONFIG="$REMOTE.kubeconfig"
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
    --connection)
        if [[ "$COMMAND" != "remove" ]]; then
            print_error "--connection is only valid for the 'remove' command"
            VALIDATION_ERRORS=1
        else
            REMOVE_CONNECTION="connection"
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
        print_error "Unknown option: $1"
        echo "Use '--help' to see available options for the '$COMMAND' command"
        exit 1
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
create-manager-cluster)
    create_cluster
    ;;
install)
    install_kueue
    ;;
configure)
    if [[ "$CLUSTER_MODE" = "local" ]]; then
        configure_manager
    else
        configure_remote
    fi
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
        status_kueue
    fi
    ;;
test)
    if [[ "$CLUSTER_MODE" != "remote" ]]; then
        print_error "Please specify a remote cluster to test with --remote."
        exit 1
    fi

    # Only continue if no errors in check_remote_cluster_connection
    if ! check_remote_cluster_connection; then
        print_error "Remote cluster connection check failed. Aborting test."
        exit 1
    fi

    chmod +x ./test-remote-multikueue.sh && ./test-remote-multikueue.sh --remote "$REMOTE"
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
