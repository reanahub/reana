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
KUBECONFIG_FLAG=""

# Default config for configure command
BATCH_CPU=2
BATCH_MEMORY=3Gi
JOB_CPU=4
JOB_MEMORY=7Gi

# Default config for monitor command
MONITOR_REFRESH_INTERVAL_SECS=3

# Default config for remove command
REMOVE_ALL=false
REMOVE_WORKLOADS=false
REMOVE_RESOURCES=false
REMOVE_KUEUE=false

# Helper functions
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_section() {
    echo -e "${BLUE}$1${NC}"
}

run_cmd() {
    echo -e "${YELLOW}$ $*${NC}"
    "$@"
}

# Check if Kueue is installed
is_kueue_installed() {
    kubectl ${KUBECONFIG_FLAG} get namespace kueue-system &>/dev/null
}

# Wait for resource cleanup with timeout
wait_for_cleanup() {
    local resource_type="$1"
    local namespace_flag="$2"
    local timeout=30
    local count=0

    print_info "Waiting for $resource_type cleanup..."
    while [ $count -lt $timeout ]; do
        if [ "$(kubectl ${KUBECONFIG_FLAG} get "$resource_type" "$namespace_flag" --no-headers 2>/dev/null | wc -l)" -eq 0 ]; then
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
    kubectl ${KUBECONFIG_FLAG} get "$resource_type" --no-headers 2>/dev/null | while read -r resource_name rest; do
        echo "Resource name: $resource_name"

        echo -e "${BLUE}   - Deleting $resource_type $resource_name...${NC}"
        kubectl ${KUBECONFIG_FLAG} delete "$resource_type" "$resource_name" --all-namespaces --ignore-not-found=true --timeout=20s
    done
}

# Force delete resources
force_delete_resources() {
    local resource_type="$1"
    local namespace_flag="$2"

    print_info "Force deleting $resource_type resources..."
    kubectl ${KUBECONFIG_FLAG} get "$resource_type" "$namespace_flag" --no-headers 2>/dev/null | while read -r namespace_or_name name_or_rest rest; do
        if [[ "$namespace_flag" == "-A" ]]; then
            local ns="-n $namespace_or_name"
            local name="$name_or_rest"
        else
            local ns="$namespace_flag"
            local name="$namespace_or_name"
        fi

        kubectl ${KUBECONFIG_FLAG} patch "$resource_type" "$name" "$ns" --type merge --patch '{"metadata":{"finalizers":[]}}' 2>/dev/null || true
        kubectl ${KUBECONFIG_FLAG} delete "$resource_type" "$name" "$ns" --force --grace-period=0 --ignore-not-found=true 2>/dev/null || true
    done
}

# Count and display resources
count_and_display_resources() {
    local resource_type="$1"
    local namespace_flag="$2"
    local display_name="$3"

    local raw_count
    raw_count=$(kubectl ${KUBECONFIG_FLAG} "${KUBECONFIG_FLAG}" get "$resource_type" "$namespace_flag" --no-headers 2>/dev/null | wc -l)

    # Trim the raw count output
    local count
    count=$(echo "$raw_count" | tr -d '[:space:]')

    if [ "$count" -gt 0 ]; then
        echo -e "${BLUE} - $display_name ($count found):${NC}"
        kubectl ${KUBECONFIG_FLAG} "${KUBECONFIG_FLAG}" get "$resource_type" "$namespace_flag" --no-headers 2>/dev/null | while read -r line; do
            echo -e "${YELLOW}   • $line${NC}"
        done
        return 0 # Success - resources found
    else
        print_status "No $display_name found"
        return 1 # No resources found
    fi
}

# Comprehensive resource verification
verify_kueue_resources() {
    local mode="$1" # "check" or "final"

    if [ "$mode" = "final" ]; then
        print_section "🔍 Final verification of Kueue resources..."
    else
        print_section "🔍 Checking Kueue resources..."
    fi

    local has_resources=false

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
    if [ "$has_resources" = "true" ] && [ "$mode" = "final" ]; then
        return 0 # Resources found
    else
        return 1 # No resources found
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
    # Check for Kind cluster
    # shellcheck disable=SC2086
    if ! kubectl ${KUBECONFIG_FLAG} get nodes | grep -q "Ready"; then
        print_error "Could not find Kind cluster."
        exit 1
    fi

    if is_kueue_installed; then
        print_status "Kueue is already installed"
        return 0
    fi

    print_section "📦 Installing Kueue..."
    run_cmd helm install kueue oci://registry.k8s.io/kueue/charts/kueue \
        --version=0.13.2 \
        --namespace kueue-system \
        --create-namespace \
        ${KUBECONFIG_FLAG} \
        --wait --timeout 300s

    # Use `check_crds_installed "false"` to verify installation
    if check_crds_installed "check"; then
        print_status "Kueue installed successfully"
    else
        print_error "There were problems while installing Kueue. It may not be installed or some CRDs may be missing. Run '$0 status' to check. If only CRDs are missing, please run '$0 remove' and try installing again."
    fi
}

# Configure Kueue
configure_kueue() {
    if ! is_kueue_installed; then
        print_error "Kueue is not installed. Please run 'install' command first."
        return 1
    fi

    print_section "📄 Applying Kueue resource manifests..."
    print_info "Batch : ${BATCH_CPU} CPU | ${BATCH_MEMORY} memory"
    print_info "Job   : ${JOB_CPU} CPU | ${JOB_MEMORY} memory"

    cat <<EOF | kubectl ${KUBECONFIG_FLAG} apply -f -
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: ResourceFlavor
metadata:
  name: "default-flavor"
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: LocalQueue
metadata:
  namespace: "default"
  name: "local-queue-batch"
spec:
  clusterQueue: "cluster-queue-reana-run-batch"
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: ClusterQueue
metadata:
  name: "cluster-queue-reana-run-batch"
spec:
  namespaceSelector: {}
  admissionChecks:
    - remote-multikueue-admission-check
  resourceGroups:
  - coveredResources: ["cpu", "memory"]
    flavors:
    - name: "default-flavor"
      resources:
      - name: "cpu"
        nominalQuota: ${BATCH_CPU}
      - name: "memory"
        nominalQuota: ${BATCH_MEMORY}
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: LocalQueue
metadata:
  namespace: "default"
  name: "local-queue-job"
spec:
  clusterQueue: "cluster-queue-reana-run-job"
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: ClusterQueue
metadata:
  name: "cluster-queue-reana-run-job"
spec:
  namespaceSelector: {}
  admissionChecks:
    - remote-multikueue-admission-check
  resourceGroups:
  - coveredResources: ["cpu", "memory"]
    flavors:
    - name: "default-flavor"
      resources:
      - name: "cpu"
        nominalQuota: ${JOB_CPU}
      - name: "memory"
        nominalQuota: ${JOB_MEMORY}
EOF

    print_status "ClusterQueue, LocalQueue, and ResourceFlavor applied"
    print_info "Verifying resources..."
    sleep 3

    verify_kueue_resources "check"
}

# Handle workload removal/preservation
remove_workloads() {
    local workload_count
    workload_count=$(kubectl ${KUBECONFIG_FLAG} get workloads -A --no-headers 2>/dev/null | wc -l)

    print_section "🚧 Removing active Kueue workloads and associated jobs..."

    if [ "$workload_count" -gt 0 ]; then
        print_info "Found $workload_count workload(s), removing workloads and their parent jobs..."
        count_and_display_resources "workloads" "-A" "Active workloads"

        # First, find and remove the associated Jobs to prevent workload recreation
        print_info "Identifying and removing parent Jobs..."
        kubectl ${KUBECONFIG_FLAG} get jobs -A -o json 2>/dev/null | jq -r '.items[] | select(.metadata.labels["kueue.x-k8s.io/queue-name"] != null or .metadata.annotations["kueue.x-k8s.io/queue-name"] != null) | "\(.metadata.namespace) \(.metadata.name)"' | while read -r namespace job_name; do
            if [ -n "$namespace" ] && [ -n "$job_name" ]; then
                echo -e "${BLUE}   - Deleting Job $job_name in namespace $namespace...${NC}"
                kubectl ${KUBECONFIG_FLAG} delete job "$job_name" -n "$namespace" --ignore-not-found=true --timeout=30s
            fi
        done

        # Also remove any jobs that might have workloads associated (broader search)
        kubectl ${KUBECONFIG_FLAG} get workloads -A --no-headers 2>/dev/null | while read -r namespace workload_name rest; do
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
            if kubectl ${KUBECONFIG_FLAG} get job "$potential_job_name" -n "$namespace" &>/dev/null; then
                echo -e "${BLUE}   - Deleting associated Job $potential_job_name in namespace $namespace...${NC}"
                kubectl ${KUBECONFIG_FLAG} delete job "$potential_job_name" -n "$namespace" --ignore-not-found=true --timeout=30s
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
            remaining_workloads=$(kubectl ${KUBECONFIG_FLAG} get workloads -A --no-headers 2>/dev/null | wc -l)
            local remaining_kueue_jobs
            remaining_kueue_jobs=$(kubectl ${KUBECONFIG_FLAG} get jobs -A -o json 2>/dev/null | jq -r '.items[] | select(.metadata.labels["kueue.x-k8s.io/queue-name"] != null or .metadata.annotations["kueue.x-k8s.io/queue-name"] != null)' 2>/dev/null | jq -s length 2>/dev/null || echo "0")

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
        remaining=$(kubectl ${KUBECONFIG_FLAG} get workloads -A --no-headers 2>/dev/null | wc -l)

        if [ "$remaining" -gt 0 ]; then
            print_warning "Some workloads still exist, forcing deletion..."
            force_delete_resources "workloads" "-A"

            # Force delete any remaining Kueue jobs
            kubectl ${KUBECONFIG_FLAG} get jobs -A -o json 2>/dev/null | jq -r '.items[] | select(.metadata.labels["kueue.x-k8s.io/queue-name"] != null or .metadata.annotations["kueue.x-k8s.io/queue-name"] != null) | "\(.metadata.namespace) \(.metadata.name)"' | while read -r namespace job_name; do
                if [ -n "$namespace" ] && [ -n "$job_name" ]; then
                    echo -e "${BLUE}   - Force deleting Job $job_name in namespace $namespace...${NC}"
                    kubectl ${KUBECONFIG_FLAG} patch job "$job_name" -n "$namespace" --type merge --patch '{"metadata":{"finalizers":[]}}' 2>/dev/null || true
                    kubectl ${KUBECONFIG_FLAG} delete job "$job_name" -n "$namespace" --force --grace-period=0 --ignore-not-found=true 2>/dev/null || true
                fi
            done
        fi

        # Final check
        remaining=$(kubectl ${KUBECONFIG_FLAG} get workloads -A --no-headers 2>/dev/null | wc -l)
        local remaining_jobs
        remaining_jobs=$(kubectl ${KUBECONFIG_FLAG} get jobs -A -o json 2>/dev/null | jq -r '.items[] | select(.metadata.labels["kueue.x-k8s.io/queue-name"] != null or .metadata.annotations["kueue.x-k8s.io/queue-name"] != null)' 2>/dev/null | jq -s length 2>/dev/null || echo "0")

        if [ "$remaining" -eq 0 ] && [ "$remaining_jobs" -eq 0 ]; then
            print_status "All workloads and associated jobs removed"
        else
            print_warning "$remaining workloads and $remaining_jobs Kueue jobs still exist after cleanup"
            if [ "$remaining" -gt 0 ]; then
                print_info "Remaining workloads:"
                kubectl ${KUBECONFIG_FLAG} get workloads -A 2>/dev/null || true
            fi
            if [ "$remaining_jobs" -gt 0 ]; then
                print_info "Remaining Kueue jobs:"
                kubectl ${KUBECONFIG_FLAG} get jobs -A -o json 2>/dev/null | jq -r '.items[] | select(.metadata.labels["kueue.x-k8s.io/queue-name"] != null or .metadata.annotations["kueue.x-k8s.io/queue-name"] != null) | "\(.metadata.namespace)\t\(.metadata.name)"' 2>/dev/null || true
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
    force_delete_resources "localqueue" ""

    # Delete any remaining ClusterQueues
    print_section " - Removing ClusterQueues..."
    force_delete_resources "clusterqueue" ""

    # Delete ResourceFlavors
    print_section " - Removing ResourceFlavors..."
    force_delete_resources "resourceflavor" ""

    print_status "Kueue resources removed"
}

# Remove Kueue helm installation
remove_kueue_installation() {
    if ! is_kueue_installed; then
        print_status "Kueue is not installed"
        return 0
    fi

    print_section "📦 Uninstalling Kueue..."
    if ! helm uninstall kueue -n kueue-system --wait --timeout 10s; then
        # Check if error was a timeout
        if helm status kueue -n kueue-system >/dev/null 2>&1; then
            print_warning "Helm uninstall timed out, retrying again..."
            helm uninstall kueue -n kueue-system --wait --timeout 10s
            print_status "Kueue uninstalled successfully"
        else
            print_status "Release already gone"
        fi
    fi

    print_section " - Removing Kueue namespace..."
    force_delete_resources "namespace" "kueue-system"
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
    [ "$should_remove_resources" = "true" ] && echo -e "${BLUE}  • Kueue Resources (queues, flavors)${NC}"
    [ "$should_remove_kueue" = "true" ] && echo -e "${BLUE}  • Kueue Installation (Helm chart)${NC}"
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
        if verify_kueue_resources "final"; then
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

    local kueue_crds=("clusterqueues.kueue.x-k8s.io" "localqueues.kueue.x-k8s.io" "resourceflavors.kueue.x-k8s.io" "workloads.kueue.x-k8s.io")
    local crd_count=0

    for crd in "${kueue_crds[@]}"; do
        if kubectl ${KUBECONFIG_FLAG} get crd "$crd" &>/dev/null; then
            local version
            version=$(kubectl ${KUBECONFIG_FLAG} get crd "$crd" -o jsonpath='{.spec.versions[0].name}' 2>/dev/null || echo "unknown")
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
    # Use the kubeconfig file name (without the file extension) as the secret name
    local kubeconfig_name
    kubeconfig_name="$(basename "$REMOTE_KUBECONFIG" .yaml)"

    local secret_name="remote-secret-$kubeconfig_name"

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

    run_cmd kubectl apply -f - <<EOF
---
# MultiKueueCluster for remote worker
apiVersion: kueue.x-k8s.io/v1beta1
kind: MultiKueueCluster
metadata:
  name: remote-cluster-$kubeconfig_name
  namespace: kueue-system
spec:
  kubeConfig:
    locationType: Secret
    location: $secret_name
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: MultiKueueConfig
metadata:
  name: remote-multikueue-config-$kubeconfig_name
  namespace: kueue-system
spec:
  clusters:
  - remote-cluster-$kubeconfig_name
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: AdmissionCheck
metadata:
  name: remote-multikueue-admission-check
  namespace: kueue-system
spec:
  controllerName: kueue.x-k8s.io/multikueue
  parameters:
    apiGroup: kueue.x-k8s.io
    kind: MultiKueueConfig
    name: remote-multikueue-config-$kubeconfig_name
EOF

    print_status "MultiKueueCluster connection created using kubeconfig: $REMOTE_KUBECONFIG"
}

# Status check for Kueue
status_kueue() {
    print_section "📊 Kueue Status Report"
    echo ""

    # Check if Kueue is enabled in values.yaml
    if [ "$CLUSTER_MODE" = "local" ]; then
        print_section "⚙️  Configuration Check"
        local values_file
        values_file="$(dirname "$0")/../helm/reana/values.yaml"
        local kueue_enabled_in_config=false
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
    if is_kueue_installed; then
        print_status "Kueue is installed"

        # Check Helm release info
        if helm list -n kueue-system | grep -q kueue; then
            local version
            version=$(helm list -n kueue-system -o json | jq -r '.[] | select(.name=="kueue") | .app_version' 2>/dev/null || echo "unknown")
            print_info "Helm release found (version: $version)"
        else
            print_warning "Kueue namespace exists but Helm release not found (maybe Kueue was installed via kubectl?)"
        fi

        # Check pod status in kueue-system namespace
        print_info "Pod status in kueue-system:"
        kubectl ${KUBECONFIG_FLAG} get pods -n kueue-system --no-headers 2>/dev/null | while read -r name ready status age; do
            if [[ "$status" == "Running" ]]; then
                echo -e "${GREEN}   ✅ $name: $status ($ready ready)${NC}"
            else
                echo -e "${YELLOW}   ⚠️  $name: $status ($ready ready)${NC}"
            fi
        done
    else
        print_error "Kueue is not installed"
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
    rf_count=$(kubectl ${KUBECONFIG_FLAG} get resourceflavors --no-headers 2>/dev/null | wc -l)

    if [ "$rf_count" -gt 0 ]; then
        print_info "Found $rf_count ResourceFlavor(s):"
        kubectl ${KUBECONFIG_FLAG} get resourceflavors --no-headers 2>/dev/null | while read -r name age; do
            echo -e "${BLUE}   • $name (age: $age)${NC}"
        done
    else
        print_warning "No ResourceFlavors found"
    fi
    echo ""

    # Check ClusterQueues
    print_section "🏢 ClusterQueues"
    local cq_count
    cq_count=$(kubectl ${KUBECONFIG_FLAG} get clusterqueues --no-headers 2>/dev/null | wc -l)

    if [ "$cq_count" -gt 0 ]; then
        print_info "Found $cq_count ClusterQueue(s):"
        kubectl ${KUBECONFIG_FLAG} get clusterqueues -o custom-columns="NAME:.metadata.name,COHORT:.spec.cohort,PENDING:.status.pendingWorkloads,ADMITTED:.status.admittedWorkloads" --no-headers 2>/dev/null | while read -r line; do
            echo -e "${BLUE}   • $line${NC}"
        done

        # Show resource quotas for each ClusterQueue
        echo ""
        print_info "Resource quotas per ClusterQueue:"
        kubectl ${KUBECONFIG_FLAG} get clusterqueues -o json 2>/dev/null | jq -r '.items[] | "\(.metadata.name): " + (.spec.resourceGroups[0].flavors[0].resources | map("\(.name)=\(.nominalQuota)") | join(", "))' | while read -r line; do
            echo -e "${NC}   📊 $line${NC}"
        done
    else
        print_warning "No ClusterQueues found"
    fi
    echo ""

    # Check LocalQueues
    print_section "🏪 LocalQueues"
    local lq_count
    lq_count=$(kubectl ${KUBECONFIG_FLAG} get localqueues -A --no-headers 2>/dev/null | wc -l)

    if [ "$lq_count" -gt 0 ]; then
        print_info "Found $lq_count LocalQueue(s):"
        kubectl ${KUBECONFIG_FLAG} get localqueues -A -o custom-columns="NAMESPACE:.metadata.namespace,NAME:.metadata.name,CLUSTERQUEUE:.spec.clusterQueue,PENDING:.status.pendingWorkloads,ADMITTED:.status.admittedWorkloads" --no-headers 2>/dev/null | while read -r line; do
            echo -e "${BLUE}   • $line${NC}"
        done
    else
        print_warning "No LocalQueues found"
    fi
    echo ""

    # Check active Workloads
    print_section "⚡ Active Workloads"
    local workload_count
    workload_count=$(kubectl ${KUBECONFIG_FLAG} get workloads -A --no-headers 2>/dev/null | wc -l)

    if [ "$workload_count" -gt 0 ]; then
        print_info "Found $workload_count active workload(s):"
        kubectl ${KUBECONFIG_FLAG} get workloads -A -o custom-columns="NAMESPACE:.metadata.namespace,NAME:.metadata.name,QUEUE:.spec.queueName,ADMITTED:.status.conditions[?(@.type=='Admitted')].status" --no-headers 2>/dev/null | while read -r line; do
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
    kueue_jobs=$(kubectl ${KUBECONFIG_FLAG} get jobs -A -o json 2>/dev/null | jq -r '.items[] | select(.metadata.labels["kueue.x-k8s.io/queue-name"] != null or .metadata.annotations["kueue.x-k8s.io/queue-name"] != null)' 2>/dev/null | jq -s length 2>/dev/null || echo "0")

    if [ "$kueue_jobs" -gt 0 ]; then
        print_info "Found $kueue_jobs Kueue-managed job(s):"
        kubectl ${KUBECONFIG_FLAG} get jobs -A -o json 2>/dev/null | jq -r '.items[] | select(.metadata.labels["kueue.x-k8s.io/queue-name"] != null or .metadata.annotations["kueue.x-k8s.io/queue-name"] != null) | "\(.metadata.namespace) \(.metadata.name) \(.metadata.labels["kueue.x-k8s.io/queue-name"] // .metadata.annotations["kueue.x-k8s.io/queue-name"] // "N/A") \(.status.conditions[-1].type // "Unknown")"' 2>/dev/null | while read -r namespace name queue status; do
            if [[ "$status" == "Complete" ]]; then
                echo -e "${GREEN}   ✅ $namespace/$name (queue: $queue, status: $status)${NC}"
            elif [[ "$status" == "Failed" ]]; then
                echo -e "${RED}   ❌ $namespace/$name (queue: $queue, status: $status)${NC}"
            else
                echo -e "${YELLOW}   ⏳ $namespace/$name (queue: $queue, status: $status)${NC}"
            fi
        done
    else
        print_info "No Kueue-managed jobs found"
    fi
    echo ""

    # Check recent Kueue events
    print_section "📰 Recent Kueue Events (last 10)"
    local events
    events=$(kubectl ${KUBECONFIG_FLAG} get events -A --field-selector reason=Admitted,reason=QuotaReserved,reason=Preempted,reason=Evicted --sort-by='.lastTimestamp' 2>/dev/null | tail -10)

    if [[ -n "$events" && "$events" != *"No resources found"* ]]; then
        echo "$events" | while IFS= read -r line; do
            if [[ "$line" == *"LAST SEEN"* ]]; then
                echo -e "${BLUE}$line${NC}"
            elif [[ "$line" == *"Admitted"* ]]; then
                echo -e "${GREEN}$line${NC}"
            elif [[ "$line" == *"Preempted"* || "$line" == *"Evicted"* ]]; then
                echo -e "${RED}$line${NC}"
            else
                echo -e "${YELLOW}$line${NC}"
            fi
        done
    else
        print_info "No recent Kueue events found"
    fi
    echo ""

    # Check connections to remote clusters
    if [ "$CLUSTER_MODE" = "local" ]; then
        print_section "🌍 Remote Cluster Connections"

        local remote_clusters
        remote_clusters=$(kubectl get multikueueconfigs -n kueue-system --no-headers 2>/dev/null | wc -l)

        if [ "$remote_clusters" -gt 0 ]; then
            print_info "Found $remote_clusters remote cluster(s):"
            kubectl get multikueueconfigs -n kueue-system --no-headers 2>/dev/null | while read -r line; do
                # Remove leading 'remote-multikueue-config-' from each line
                line=${line#remote-multikueue-config-}
                echo -e "${BLUE}   • $line${NC}"
            done
        else
            print_info "No remote clusters connected"
        fi
        echo ""
    fi

    # Summary
    print_section "📝 Summary"
    if is_kueue_installed; then
        local rf_count cq_count lq_count wl_count
        rf_count=$(kubectl ${KUBECONFIG_FLAG} get resourceflavors --no-headers 2>/dev/null | wc -l || echo 0)
        rf_count=$(echo "$rf_count" | tr -d '[:space:]')

        cq_count=$(kubectl ${KUBECONFIG_FLAG} get clusterqueues --no-headers 2>/dev/null | wc -l || echo 0)
        cq_count=$(echo "$cq_count" | tr -d '[:space:]')

        lq_count=$(kubectl ${KUBECONFIG_FLAG} get localqueues -A --no-headers 2>/dev/null | wc -l || echo 0)
        lq_count=$(echo "$lq_count" | tr -d '[:space:]')

        wl_count=$(kubectl ${KUBECONFIG_FLAG} get workloads -A --no-headers 2>/dev/null | wc -l || echo 0)
        wl_count=$(echo "$wl_count" | tr -d '[:space:]')

        if [ "$rf_count" -gt 0 ] && [ "$cq_count" -gt 0 ] && [ "$lq_count" -gt 0 ]; then
            if $kueue_enabled_in_config; then
                print_status "Kueue is installed, enabled in config, and configured with $rf_count ResourceFlavor(s), $cq_count ClusterQueue(s), and $lq_count LocalQueue(s)"
            else
                print_warning "Kueue is installed and configured but NOT enabled in values.yaml so Kueue will not be used. Enable it and redeploy your cluster to use Kueue."
            fi

            if [ "$wl_count" -gt 0 ]; then
                print_info "Currently processing $wl_count workload(s)"
            else
                print_info "No active workloads"
            fi
        elif [ "$rf_count" -eq 0 ] || [ "$cq_count" -eq 0 ] || [ "$lq_count" -eq 0 ]; then
            print_warning "Kueue is installed but not fully configured (missing queues or flavors)"
        fi
    else
        print_error "Kueue is not installed"
        print_info "Run '$0 install$(if [ "$CLUSTER_MODE" = "remote" ]; then echo " --remote"; fi)' to install Kueue"
    fi
}

check_remote_cluster_connection() {
    local errors_present=false
    print_section "Checking Remote MultiKueue Setup"

    # Test connection to remote cluster
    print_info "Testing connection to remote cluster..."
    if ! run_cmd kubectl --kubeconfig="$REMOTE_KUBECONFIG" get namespaces >/dev/null 2>&1; then
        print_error "Cannot connect to remote cluster. Please check your kubeconfig."
        errors_present=true
    else
        print_status "Connected to remote cluster."

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

        # Verify that the same LocalQueue exists here and on the remote cluster
        print_info "Verifying LocalQueue setup..."
        if ! kubectl get localqueue local-queue-batch >/dev/null 2>&1; then
            print_error "LocalQueue 'local-queue-batch' not found on manager cluster."
            errors_present=true
        fi
        if ! kubectl --kubeconfig="$REMOTE_KUBECONFIG" get localqueue local-queue-batch >/dev/null 2>&1; then
            print_error "LocalQueue 'local-queue-batch' not found on remote cluster."
            errors_present=true
        fi
        if ! kubectl get localqueue local-queue-job >/dev/null 2>&1; then
            print_error "LocalQueue 'local-queue-job' not found on manager cluster."
            errors_present=true
        fi
        if ! kubectl --kubeconfig="$REMOTE_KUBECONFIG" get localqueue local-queue-job >/dev/null 2>&1; then
            print_error "LocalQueue 'local-queue-job' not found on remote cluster."
            errors_present=true
        fi

        print_status "Remote MultiKueue configuration verified."
        echo ""
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
        kubectl ${KUBECONFIG_FLAG} get workloads -A 2>/dev/null || echo "No workloads found"
        echo
        echo "=== Jobs with Kueue Labels/Annotations ==="
        kubectl ${KUBECONFIG_FLAG} get jobs -A -o json 2>/dev/null | jq -r '.items[] | select(.metadata.labels["kueue.x-k8s.io/queue-name"] != null or .metadata.annotations["kueue.x-k8s.io/queue-name"] != null) | "\(.metadata.namespace)\t\(.metadata.name)\t\(.metadata.labels["kueue.x-k8s.io/queue-name"] // .metadata.annotations["kueue.x-k8s.io/queue-name"] // "N/A")"' 2>/dev/null || echo "No Kueue-managed jobs"
        echo
        echo "=== Queue Status ==="
        kubectl ${KUBECONFIG_FLAG} get localqueues,clusterqueues -A 2>/dev/null
        echo
        echo "=== Recent Events (Kueue-related) ==="
        kubectl ${KUBECONFIG_FLAG} get events -A --field-selector reason=Admitted,reason=QuotaReserved,reason=Preempted --sort-by='.lastTimestamp' 2>/dev/null | tail -5
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
        echo "  --batch-cpu          : Set batch queue CPU core quota (default: ${BATCH_CPU})"
        echo "  --batch-memory       : Set batch queue memory quota (default: ${BATCH_MEMORY})"
        echo "  --job-cpu            : Set job queue CPU quota (default: ${JOB_CPU})"
        echo "  --job-memory         : Set job queue memory quota (default: ${JOB_MEMORY})"
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
    connect-remote)
        echo "USAGE:"
        echo "  $0 connect-remote [--help]"
        echo ""
        echo "DESCRIPTION:"
        echo "  Connect to remote cluster (requires REMOTE_KUBECONFIG environment variable to be set)"
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
        echo "  Check Kueue installation status"
        echo ""
        echo "OPTIONS:"
        echo "  --help, -h           : Display this help message"
        ;;
    test-remote)
        echo "USAGE:"
        echo "  $0 test-remote [--help]"
        echo ""
        echo "DESCRIPTION:"
        echo "  Test MultiKueue setup with remote cluster using a sample job"
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
        echo "  connect-remote       : Connect to remote cluster (requires REMOTE_KUBECONFIG environment variable to be set)"
        echo "  monitor              : Monitor active Kueue workloads and jobs"
        echo "  remove               : Remove Kueue components"
        echo "  status               : Check Kueue installation status"
        echo "  test-remote          : Test MultiKueue setup with remote cluster using a sample job"
        echo ""
        echo "GLOBAL OPTIONS:"
        echo "  --local              : Operate on local cluster (default)"
        echo "  --remote             : Operate on remote cluster (requires REMOTE_KUBECONFIG environment variable to be set)"
        echo "  --help, -h           : Show help for command or general usage"
        echo ""
        echo "EXAMPLES:"
        echo "  $0 install"
        echo "  $0 configure --batch-cpu 4 --job-memory 8Gi"
        echo "  $0 monitor --refresh-interval 5"
        echo "  $0 remove --kueue --resources"
        echo "  $0 remove --workloads"
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
        if [ "$COMMAND" = "create-manager-cluster" ] || [ "$COMMAND" = "connect-remote" ] || [ "$COMMAND" = "test-remote" ]; then
            print_error "--remote is not valid for the '$COMMAND' command"
            VALIDATION_ERRORS=1
        fi

        # Check if REMOTE_KUBECONFIG is provided
        if [ -z "${REMOTE_KUBECONFIG:-}" ]; then
            print_error "REMOTE_KUBECONFIG environment variable must be set"
            print_info "Usage: export REMOTE_KUBECONFIG=/path/to/kubeconfig"
            exit 1
        fi

        # Verify kubeconfig file exists
        if [ ! -f "$REMOTE_KUBECONFIG" ]; then
            print_error "Kubeconfig file not found: $REMOTE_KUBECONFIG"
            exit 1
        fi

        CLUSTER_MODE="remote"
        KUBECONFIG_FLAG="--kubeconfig=$REMOTE_KUBECONFIG"
        ;;
    --batch-cpu)
        if [[ "$COMMAND" != "configure" ]]; then
            print_error "--batch-cpu is only valid for the 'configure' command"
            VALIDATION_ERRORS=1
        elif [[ -z "$2" ]]; then
            print_error "--batch-cpu requires a value"
            VALIDATION_ERRORS=1
        else
            if validate_cpu "$2" "batch CPU"; then
                BATCH_CPU="$2"
            else
                VALIDATION_ERRORS=1
            fi
            shift
        fi
        ;;
    --batch-memory)
        if [[ "$COMMAND" != "configure" ]]; then
            print_error "--batch-memory is only valid for the 'configure' command"
            VALIDATION_ERRORS=1
        elif [[ -z "$2" ]]; then
            print_error "--batch-memory requires a value"
            VALIDATION_ERRORS=1
        else
            if validate_memory "$2" "batch memory"; then
                BATCH_MEMORY="$2"
            else
                VALIDATION_ERRORS=1
            fi
            shift
        fi
        ;;
    --job-cpu)
        if [[ "$COMMAND" != "configure" ]]; then
            print_error "--job-cpu is only valid for the 'configure' command"
            VALIDATION_ERRORS=1
        elif [[ -z "$2" ]]; then
            print_error "--job-cpu requires a value"
            VALIDATION_ERRORS=1
        else
            if validate_cpu "$2" "job CPU"; then
                JOB_CPU="$2"
            else
                VALIDATION_ERRORS=1
            fi
            shift
        fi
        ;;
    --job-memory)
        if [[ "$COMMAND" != "configure" ]]; then
            print_error "--job-memory is only valid for the 'configure' command"
            VALIDATION_ERRORS=1
        elif [[ -z "$2" ]]; then
            print_error "--job-memory requires a value"
            VALIDATION_ERRORS=1
        else
            if validate_memory "$2" "job memory"; then
                JOB_MEMORY="$2"
            else
                VALIDATION_ERRORS=1
            fi
            shift
        fi
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
    configure_kueue
    ;;
connect-remote)
    connect_remote_cluster
    ;;
monitor)
    monitor_kueue
    ;;
remove)
    handle_remove
    ;;
status)
    if [[ "$CLUSTER_MODE" = "remote" ]]; then
        check_remote_cluster_connection
    fi
    status_kueue
    ;;
test-remote)
    # Only continue if no errors in check_remote_cluster_connection
    if ! check_remote_cluster_connection; then
        print_error "Remote cluster connection check failed. Aborting test."
        exit 1
    fi

    ./test-remote-multikueue.sh
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
