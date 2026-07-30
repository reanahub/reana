#!/usr/bin/env bash
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

# Manage CERN reverse-DNS forwarding for local k3s development clusters.

set -o errexit
set -o nounset
set -o pipefail

readonly COREDNS_NAMESPACE="kube-system"
readonly COREDNS_CONFIGMAP="coredns-custom"
readonly COREDNS_DEPLOYMENT="coredns"
readonly COREDNS_DATA_KEY="cern-reverse.server"
SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
readonly SCRIPT_DIRECTORY
readonly MANIFEST_PATH="${SCRIPT_DIRECTORY}/../etc/cern-coredns-local.yaml"

usage() {
    echo "Usage: $0 {install|status|remove}"
    echo
    echo "Manage CERN reverse-DNS forwarding in a local k3s cluster."
    echo "The cluster must be connected to the CERN VPN."
}

print_error() {
    echo "Error: $*" >&2
}

require_kubectl() {
    if ! command -v kubectl >/dev/null 2>&1; then
        print_error "kubectl is required."
        exit 1
    fi
}

check_supported_cluster() {
    local corefile

    if ! corefile=$(kubectl get configmap coredns \
        --namespace "${COREDNS_NAMESPACE}" \
        --output go-template='{{ index .data "Corefile" }}'); then
        print_error "Cannot read the CoreDNS configuration."
        exit 1
    fi

    if [[ "${corefile}" != *'import /etc/coredns/custom/*.server'* ]]; then
        print_error "CoreDNS does not import coredns-custom server files."
        print_error "This helper currently supports local k3s clusters only."
        exit 1
    fi
}

get_installed_fragment() {
    kubectl get configmap "${COREDNS_CONFIGMAP}" \
        --namespace "${COREDNS_NAMESPACE}" \
        --ignore-not-found \
        --output "go-template={{ with .data }}{{ with index . \"${COREDNS_DATA_KEY}\" }}{{ . }}{{ end }}{{ end }}"
}

restart_coredns() {
    kubectl rollout restart "deployment/${COREDNS_DEPLOYMENT}" \
        --namespace "${COREDNS_NAMESPACE}"
    kubectl rollout status "deployment/${COREDNS_DEPLOYMENT}" \
        --namespace "${COREDNS_NAMESPACE}" \
        --timeout 60s
}

install_configuration() {
    local configmap

    check_supported_cluster
    configmap=$(kubectl get configmap "${COREDNS_CONFIGMAP}" \
        --namespace "${COREDNS_NAMESPACE}" \
        --ignore-not-found \
        --output name)

    # Create the ConfigMap when it is absent, and merge the fragment into it
    # otherwise. A merge patch keeps unrelated entries, whilst a server-side
    # apply would prune them when the ConfigMap was created by a client-side
    # apply.
    if [[ -z "${configmap}" ]]; then
        kubectl create --filename "${MANIFEST_PATH}"
    else
        kubectl patch configmap "${COREDNS_CONFIGMAP}" \
            --namespace "${COREDNS_NAMESPACE}" \
            --type merge \
            --patch-file "${MANIFEST_PATH}"
    fi

    restart_coredns
    echo "CERN reverse-DNS forwarding is installed."
}

show_status() {
    local fragment
    fragment=$(get_installed_fragment)

    if [[ -n "${fragment}" ]]; then
        echo "CERN reverse-DNS forwarding is installed."
        kubectl get "deployment/${COREDNS_DEPLOYMENT}" \
            --namespace "${COREDNS_NAMESPACE}"
    else
        echo "CERN reverse-DNS forwarding is not installed."
    fi
}

remove_configuration() {
    local fragment
    fragment=$(get_installed_fragment)

    if [[ -z "${fragment}" ]]; then
        echo "CERN reverse-DNS forwarding is not installed."
        return
    fi

    kubectl patch configmap "${COREDNS_CONFIGMAP}" \
        --namespace "${COREDNS_NAMESPACE}" \
        --type json \
        --patch "[{\"op\":\"remove\",\"path\":\"/data/${COREDNS_DATA_KEY}\"}]"
    restart_coredns
    echo "CERN reverse-DNS forwarding is removed."
}

if [[ $# -ne 1 ]]; then
    usage
    exit 1
fi

case "$1" in
-h | --help)
    usage
    exit 0
    ;;
install | status | remove) ;;
*)
    usage
    exit 1
    ;;
esac

require_kubectl
echo "Using Kubernetes context: $(kubectl config current-context)"

case "$1" in
install) install_configuration ;;
status) show_status ;;
remove) remove_configuration ;;
esac
