# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2025 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Tests for reana_dev/utils.py"""
import pytest
from unittest.mock import patch
from reana.reana_dev.kueue import (
    KueueFlavor,
    KueueQueue,
    KueueNode,
    KueueResources,
    run_cmd,
)


kueue_resources_file_path = "tests/data/kueue-resources.yaml"


class TestKueueFlavor:
    @pytest.mark.parametrize(
        "name, cpu, memory, expected_name, expected_cpu, expected_memory",
        [
            ("test", 1, "1Gi", "test", "1", "1Gi"),
            ("test", 1, "1Mi", "test", "1", "1Mi"),
            ("test", 1, "1Ti", "test", "1", "1Ti"),
            ("test123", 1, "100Gi", "test123", "1", "100Gi"),
            ("123test", "1", "100Gi", "123test", "1", "100Gi"),
            ("test ", " 1 ", " 100Gi", "test", "1", "100Gi"),
        ],
    )
    def test_valid_flavor(
        self,
        name: str,
        cpu: str | int,
        memory: str,
        expected_name: str,
        expected_cpu: int,
        expected_memory: str,
    ):
        flavor = KueueFlavor(name, cpu, memory)
        assert flavor.name == expected_name
        assert flavor.cpu == expected_cpu
        assert flavor.memory == expected_memory

    @pytest.mark.parametrize(
        "name, cpu, memory",
        [
            ("", 1, "1Gi"),
            ("test", "", "1Gi"),
            ("test", 1, ""),
            ("test", 1, "1GiB"),
            ("test", 1, "1"),
            ("test", "one", "1Gi"),
        ],
    )
    def test_invalid_flavor(self, name: str, cpu: int, memory: str):
        with pytest.raises(Exception):
            KueueFlavor(name, cpu, memory)

    def test_flavor_equality(self):
        flavor1 = KueueFlavor("test", 1, "1Gi")
        flavor2 = KueueFlavor("test", 1, "1Gi")
        flavor3 = KueueFlavor("test", 2, "1Gi")
        flavor4 = KueueFlavor("test2", 1, "1Gi")

        assert flavor1 == flavor2
        assert flavor1 != flavor3
        assert flavor1 != flavor4

    def test_flavor_hash(self):
        flavor1 = KueueFlavor("test", 1, "1Gi")
        flavor2 = KueueFlavor("test", 1, "1Gi")
        flavor3 = KueueFlavor("test", 2, "1Gi")
        flavor4 = KueueFlavor("test2", 1, "1Gi")

        assert hash(flavor1) == hash(flavor2)
        assert hash(flavor1) != hash(flavor3)
        assert hash(flavor1) != hash(flavor4)

    def test_flavor_repr(self):
        flavor = KueueFlavor("test", 4, "8Gi")
        repr_str = repr(flavor)
        assert "name: test" in repr_str
        assert "cpu: 4" in repr_str
        assert "memory: 8Gi" in repr_str


class TestKueueQueue:
    @pytest.mark.parametrize(
        "name, flavors, expected_name, expected_flavors",
        [
            (
                " test ",
                [KueueFlavor("test", 1, "1Gi")],
                "test",
                [KueueFlavor("test", 1, "1Gi")],
            ),
            (
                "test",
                [KueueFlavor("test", 1, "1Gi"), KueueFlavor("test2", 2, "2Gi")],
                "test",
                [KueueFlavor("test", 1, "1Gi"), KueueFlavor("test2", 2, "2Gi")],
            ),
        ],
    )
    def test_valid_queue(
        self, name: str, flavors: list, expected_name: str, expected_flavors: list
    ):
        queue = KueueQueue(name, flavors)
        assert queue.name == expected_name
        assert queue.flavors == expected_flavors

    @pytest.mark.parametrize(
        "name, flavors",
        [
            ("", [KueueFlavor("test", 1, "1Gi")]),
            ("test", []),
        ],
    )
    def test_invalid_queue(self, name: str, flavors: list):
        with pytest.raises(AssertionError):
            KueueQueue(name, flavors)

    def test_queue_equality(self):
        queue1 = KueueQueue("test", [KueueFlavor("test", 1, "1Gi")])
        queue2 = KueueQueue("test", [KueueFlavor("test", 1, "1Gi")])
        queue3 = KueueQueue("test", [KueueFlavor("test", 2, "1Gi")])
        queue4 = KueueQueue("test2", [KueueFlavor("test", 1, "1Gi")])

        assert queue1 == queue2
        assert queue1 != queue3
        assert queue1 != queue4

    def test_queue_hash(self):
        queue1 = KueueQueue("test", [KueueFlavor("test", 1, "1Gi")])
        queue2 = KueueQueue("test", [KueueFlavor("test", 1, "1Gi")])
        queue3 = KueueQueue("test", [KueueFlavor("test", 2, "1Gi")])
        queue4 = KueueQueue("test2", [KueueFlavor("test", 1, "1Gi")])

        assert hash(queue1) == hash(queue2)
        assert hash(queue1) != hash(queue3)
        assert hash(queue1) != hash(queue4)

    def test_queue_repr(self):
        flavor = KueueFlavor("test", 4, "8Gi")
        queue = KueueQueue("test-queue", [flavor])
        repr_str = repr(queue)
        assert "name: test-queue" in repr_str
        assert "flavors:" in repr_str
        assert "test" in repr_str


class TestKueueNode:
    @pytest.mark.parametrize(
        "name, queues, expected_name, expected_queues",
        [
            (
                " test ",
                [KueueQueue("test", [KueueFlavor("test", 1, "1Gi")])],
                "test",
                [KueueQueue("test", [KueueFlavor("test", 1, "1Gi")])],
            ),
        ],
    )
    def test_valid_node(
        self, name: str, queues: list, expected_name: str, expected_queues: list
    ):
        node = KueueNode(name, queues)
        assert node.name == expected_name
        assert node.queues == expected_queues

    @pytest.mark.parametrize(
        "name, queues",
        [
            ("", [KueueQueue("test", [KueueFlavor("test", 1, "1Gi")])]),
        ],
    )
    def test_invalid_node(self, name: str, queues: list):
        with pytest.raises(AssertionError):
            KueueNode(name, queues)

    def test_node_equality(self):
        node1 = KueueNode("test", [KueueQueue("test", [KueueFlavor("test", 1, "1Gi")])])
        node2 = KueueNode("test", [KueueQueue("test", [KueueFlavor("test", 1, "1Gi")])])
        node3 = KueueNode("test", [KueueQueue("test", [KueueFlavor("test", 2, "1Gi")])])
        node4 = KueueNode(
            "test2", [KueueQueue("test", [KueueFlavor("test", 1, "1Gi")])]
        )

        assert node1 == node2
        assert node1 != node3
        assert node1 != node4

    def test_node_hash(self):
        node1 = KueueNode("test", [KueueQueue("test", [KueueFlavor("test", 1, "1Gi")])])
        node2 = KueueNode("test", [KueueQueue("test", [KueueFlavor("test", 1, "1Gi")])])
        node3 = KueueNode("test", [KueueQueue("test", [KueueFlavor("test", 2, "1Gi")])])
        node4 = KueueNode(
            "test2", [KueueQueue("test", [KueueFlavor("test", 1, "1Gi")])]
        )

        assert hash(node1) == hash(node2)
        assert hash(node1) != hash(node3)
        assert hash(node1) != hash(node4)

    def test_node_repr(self):
        flavor = KueueFlavor("test", 4, "8Gi")
        queue = KueueQueue("test-queue", [flavor])
        node = KueueNode("test-node", [queue])
        repr_str = repr(node)
        assert "name: test-node" in repr_str
        assert "queues:" in repr_str


class TestKueueResources:
    @pytest.mark.parametrize(
        "flavors, nodes, expected_flavors, expected_nodes",
        [
            (
                [KueueFlavor("test", 1, "1Gi")],
                [
                    KueueNode(
                        "test", [KueueQueue("test", [KueueFlavor("test", 1, "1Gi")])]
                    )
                ],
                [KueueFlavor("test", 1, "1Gi")],
                [
                    KueueNode(
                        "test", [KueueQueue("test", [KueueFlavor("test", 1, "1Gi")])]
                    )
                ],
            ),
        ],
    )
    def test_valid_resources(
        self, flavors: list, nodes: list, expected_flavors: list, expected_nodes: list
    ):
        resources = KueueResources(flavors, nodes)
        assert resources.flavors == expected_flavors
        assert resources.nodes == expected_nodes

    @pytest.mark.parametrize(
        "flavors, nodes",
        [
            ([KueueFlavor("test", 1, "1Gi")], []),
        ],
    )
    def test_invalid_resources(self, flavors: list, nodes: list):
        with pytest.raises(AssertionError):
            KueueResources(flavors, nodes)

    def test_resources_equality(self):
        resources1 = KueueResources(
            [KueueFlavor("test", 1, "1Gi")],
            [KueueNode("test", [KueueQueue("test", [KueueFlavor("test", 1, "1Gi")])])],
        )
        resources2 = KueueResources(
            [KueueFlavor("test", 1, "1Gi")],
            [KueueNode("test", [KueueQueue("test", [KueueFlavor("test", 1, "1Gi")])])],
        )
        resources3 = KueueResources(
            [KueueFlavor("test", 2, "1Gi")],
            [KueueNode("test", [KueueQueue("test", [KueueFlavor("test", 1, "1Gi")])])],
        )
        resources4 = KueueResources(
            [KueueFlavor("test", 1, "1Gi")],
            [KueueNode("test2", [KueueQueue("test", [KueueFlavor("test", 1, "1Gi")])])],
        )

        assert resources1 == resources2
        assert resources1 != resources3
        assert resources1 != resources4

    def test_get_node(self):
        resources = KueueResources(
            [KueueFlavor("test_flavor1", 1, "1Gi")],
            [
                KueueNode(
                    "test_node1",
                    [
                        KueueQueue(
                            "test_queue1", [KueueFlavor("test_flavor1", 1, "1Gi")]
                        )
                    ],
                ),
                KueueNode(
                    "test_node2",
                    [
                        KueueQueue(
                            "test_queue1", [KueueFlavor("test_flavor1", 1, "1Gi")]
                        )
                    ],
                ),
            ],
        )
        assert resources.get_node("test_node1").name == "test_node1"
        assert resources.get_node("test_node2").name == "test_node2"
        assert resources.get_node("test_node3") is None

    def test_parse_resources_file(self):
        flavors, nodes = KueueResources._parse_resources_file(kueue_resources_file_path)

        assert len(flavors) == 3
        assert len(nodes) == 3

        assert flavors[0].name == "default"
        assert flavors[1].name == "highcpu"
        assert flavors[2].name == "highmem"

        assert nodes[0].name == "local"
        assert nodes[1].name == "remote1"
        assert nodes[2].name == "remote2"

        assert nodes[0].queues[0].name == "local-default-job-queue"
        assert nodes[0].queues[1].name == "local-atlas-job-queue"
        assert nodes[0].queues[2].name == "local-cms-job-queue"
        assert nodes[1].queues[0].name == "remote1-default-job-queue"
        assert nodes[2].queues[0].name == "remote2-default-job-queue"
        assert nodes[2].queues[1].name == "remote2-other-job-queue"

    def test_resources_repr(self):
        flavor = KueueFlavor("test", 4, "8Gi")
        queue = KueueQueue("test-queue", [flavor])
        node = KueueNode("test-node", [queue])
        resources = KueueResources([flavor], [node])
        repr_str = repr(resources)
        assert "flavors:" in repr_str
        assert "nodes:" in repr_str


class TestRunCmd:
    @patch("reana.reana_dev.kueue.subprocess.check_output")
    def test_run_cmd_capture_output(self, mock_check_output):
        mock_check_output.return_value = "test".encode("utf-8")
        assert run_cmd("test", False, capture_output=True) == "test"
        mock_check_output.assert_called_once_with("test", shell=True)

    @patch("reana.reana_dev.kueue.subprocess.check_call")
    def test_run_cmd_check(self, mock_check_call):
        run_cmd("test", False, check=True)
        mock_check_call.assert_called_once_with("test", shell=True)

    @patch("reana.reana_dev.kueue.subprocess.call")
    def test_run_cmd_no_check(self, mock_call):
        run_cmd("test", False)
        mock_call.assert_called_once_with("test", shell=True)

    @patch("reana.reana_dev.kueue.subprocess.check_call")
    def test_run_cmd_dry_run(self, mock_check_call):
        run_cmd("test", True)
        mock_check_call.assert_not_called()


class TestHelperFunctions:
    def test_get_kubeconfig_file(self):
        from reana.reana_dev.kueue import get_kubeconfig_file

        assert get_kubeconfig_file("remote1") == "remote1-kubeconfig.yaml"
        assert get_kubeconfig_file("my-cluster") == "my-cluster-kubeconfig.yaml"

    @pytest.mark.parametrize(
        "kubeconfig_file, expected_remote",
        [
            ("remote1-kubeconfig.yaml", "remote1"),
            ("my-cluster-kubeconfig.yaml", "my-cluster"),
            ("test-remote-cluster-kubeconfig.yaml", "test-remote-cluster"),
        ],
    )
    def test_get_remote_name_from_kubeconfig_file(
        self, kubeconfig_file: str, expected_remote: str
    ):
        from reana.reana_dev.kueue import get_remote_name_from_kubeconfig_file

        assert get_remote_name_from_kubeconfig_file(kubeconfig_file) == expected_remote

    def test_get_secret_name(self):
        from reana.reana_dev.kueue import get_secret_name

        assert get_secret_name("remote1") == "remote1-secret"
        assert get_secret_name("my-cluster") == "my-cluster-secret"

    def test_get_multikueue_cluster_name(self):
        from reana.reana_dev.kueue import get_multikueue_cluster_name

        assert get_multikueue_cluster_name("remote1") == "remote1-multikueue-cluster"
        assert (
            get_multikueue_cluster_name("my-cluster") == "my-cluster-multikueue-cluster"
        )

    def test_get_admission_check_name(self):
        from reana.reana_dev.kueue import get_admission_check_name

        assert get_admission_check_name("test-queue") == "test-queue-admission-check"
        assert (
            get_admission_check_name("my-job-queue") == "my-job-queue-admission-check"
        )

    def test_get_job_queue_name(self):
        from reana.reana_dev.kueue import get_job_queue_name

        assert get_job_queue_name("local", "default") == "local-default-job-queue"
        assert get_job_queue_name("remote1", "atlas") == "remote1-atlas-job-queue"

    def test_get_resources_file(self):
        from reana.reana_dev.kueue import get_resources_file

        assert get_resources_file("test-queue") == "test-queue-resources.yaml"
        assert get_resources_file("my-queue") == "my-queue-resources.yaml"

    @patch("reana.reana_dev.kueue.get_remotes")
    @pytest.mark.parametrize(
        "queue_name, remotes, expected",
        [
            ("remote1-default-job-queue", ["remote1", "remote2"], True),
            ("remote2-atlas-job-queue", ["remote1", "remote2"], True),
            ("local-default-job-queue", ["remote1", "remote2"], False),
            ("batch-queue", ["remote1", "remote2"], False),
            (
                "remote1-default",
                ["remote1", "remote2"],
                False,
            ),  # doesn't end with -job-queue
        ],
    )
    def test_is_mirror_job_queue(
        self, mock_get_remotes, queue_name: str, remotes: list, expected: bool
    ):
        from reana.reana_dev.kueue import is_mirror_job_queue

        mock_get_remotes.return_value = remotes
        assert is_mirror_job_queue(queue_name) == expected


class TestKubectlAndHelm:
    def test_kubectl_without_kubeconfig(self):
        from reana.reana_dev.kueue import kubectl

        assert (
            kubectl("get pods", namespace="test") == "kubectl --namespace test get pods"
        )
        assert (
            kubectl("apply -f file.yaml", namespace="test")
            == "kubectl --namespace test apply -f file.yaml"
        )

    def test_kubectl_with_kubeconfig(self):
        from reana.reana_dev.kueue import kubectl

        assert (
            kubectl("get pods", "remote1-kubeconfig.yaml", namespace="test")
            == "kubectl --kubeconfig=remote1-kubeconfig.yaml --namespace test get pods"
        )
        assert (
            kubectl("apply -f file.yaml", "test.yaml", namespace="test")
            == "kubectl --kubeconfig=test.yaml --namespace test apply -f file.yaml"
        )

    def test_helm_without_kubeconfig(self):
        from reana.reana_dev.kueue import helm

        assert helm("list") == "helm list --namespace kueue-system"
        assert (
            helm("install myapp chart/")
            == "helm install myapp chart/ --namespace kueue-system"
        )

    def test_helm_with_kubeconfig(self):
        from reana.reana_dev.kueue import helm

        assert (
            helm("list", "remote1-kubeconfig.yaml")
            == "helm --kubeconfig=remote1-kubeconfig.yaml --namespace kueue-system list"
        )
        assert (
            helm("install myapp chart/", "test.yaml")
            == "helm --kubeconfig=test.yaml --namespace kueue-system install myapp chart/"
        )


class TestFindDuplicateFlavors:
    def test_no_duplicates(self):
        from reana.reana_dev.kueue import find_duplicate_flavors

        resources = KueueResources(
            [KueueFlavor("flavor1", 1, "1Gi"), KueueFlavor("flavor2", 2, "2Gi")],
            [
                KueueNode(
                    "node1", [KueueQueue("queue1", [KueueFlavor("flavor1", 1, "1Gi")])]
                )
            ],
        )
        duplicates = find_duplicate_flavors(resources)
        assert duplicates == {}

    def test_with_duplicates(self):
        from reana.reana_dev.kueue import find_duplicate_flavors

        flavor1 = KueueFlavor("duplicate", 1, "1Gi")
        flavor2 = KueueFlavor("duplicate", 2, "2Gi")
        resources = KueueResources(
            [flavor1, flavor2],
            [
                KueueNode("node1", [KueueQueue("queue1", [flavor1])]),
                KueueNode("node2", [KueueQueue("queue2", [flavor2])]),
            ],
        )
        duplicates = find_duplicate_flavors(resources)
        assert "duplicate" in duplicates
        assert len(duplicates["duplicate"]) == 2


class TestCalcFlavorsDiff:
    def test_flavors_added(self):
        from reana.reana_dev.kueue import calc_flavors_diff

        kueue_resources = KueueResources(
            [KueueFlavor("flavor1", 1, "1Gi"), KueueFlavor("flavor2", 2, "2Gi")],
            [
                KueueNode(
                    "node1", [KueueQueue("queue1", [KueueFlavor("flavor1", 1, "1Gi")])]
                )
            ],
        )
        resources_snapshot = KueueResources(
            [KueueFlavor("flavor1", 1, "1Gi")],
            [
                KueueNode(
                    "node1", [KueueQueue("queue1", [KueueFlavor("flavor1", 1, "1Gi")])]
                )
            ],
        )

        flavors_added, flavors_modified, flavors_removed = calc_flavors_diff(
            kueue_resources, resources_snapshot
        )

        assert len(flavors_added) == 1
        assert KueueFlavor("flavor2", 2, "2Gi") in flavors_added
        assert len(flavors_modified) == 0
        assert len(flavors_removed) == 0

    def test_flavors_removed(self):
        from reana.reana_dev.kueue import calc_flavors_diff

        kueue_resources = KueueResources(
            [KueueFlavor("flavor1", 1, "1Gi")],
            [
                KueueNode(
                    "node1", [KueueQueue("queue1", [KueueFlavor("flavor1", 1, "1Gi")])]
                )
            ],
        )
        resources_snapshot = KueueResources(
            [KueueFlavor("flavor1", 1, "1Gi"), KueueFlavor("flavor2", 2, "2Gi")],
            [
                KueueNode(
                    "node1", [KueueQueue("queue1", [KueueFlavor("flavor1", 1, "1Gi")])]
                )
            ],
        )

        flavors_added, flavors_modified, flavors_removed = calc_flavors_diff(
            kueue_resources, resources_snapshot
        )

        assert len(flavors_added) == 0
        assert len(flavors_modified) == 0
        assert len(flavors_removed) == 1
        assert KueueFlavor("flavor2", 2, "2Gi") in flavors_removed

    def test_flavors_modified(self):
        from reana.reana_dev.kueue import calc_flavors_diff

        kueue_resources = KueueResources(
            [KueueFlavor("flavor1", 2, "2Gi")],  # Modified CPU
            [
                KueueNode(
                    "node1", [KueueQueue("queue1", [KueueFlavor("flavor1", 2, "2Gi")])]
                )
            ],
        )
        resources_snapshot = KueueResources(
            [KueueFlavor("flavor1", 1, "1Gi")],  # Original
            [
                KueueNode(
                    "node1", [KueueQueue("queue1", [KueueFlavor("flavor1", 1, "1Gi")])]
                )
            ],
        )

        flavors_added, flavors_modified, flavors_removed = calc_flavors_diff(
            kueue_resources, resources_snapshot
        )

        assert len(flavors_added) == 0
        assert len(flavors_modified) == 1
        assert flavors_modified[0].name == "flavor1"
        assert flavors_modified[0].cpu == "2"
        assert flavors_modified[0].memory == "2Gi"
        assert len(flavors_removed) == 0


class TestCalcNodesDiff:
    def test_nodes_added(self):
        from reana.reana_dev.kueue import calc_nodes_diff

        kueue_resources = KueueResources(
            [KueueFlavor("flavor1", 1, "1Gi")],
            [
                KueueNode(
                    "node1", [KueueQueue("queue1", [KueueFlavor("flavor1", 1, "1Gi")])]
                ),
                KueueNode(
                    "node2", [KueueQueue("queue2", [KueueFlavor("flavor1", 1, "1Gi")])]
                ),
            ],
        )
        resources_snapshot = KueueResources(
            [KueueFlavor("flavor1", 1, "1Gi")],
            [
                KueueNode(
                    "node1", [KueueQueue("queue1", [KueueFlavor("flavor1", 1, "1Gi")])]
                )
            ],
        )

        nodes_added, nodes_removed = calc_nodes_diff(
            kueue_resources, resources_snapshot
        )

        assert nodes_added == {"node2"}
        assert nodes_removed == set()

    def test_nodes_removed(self):
        from reana.reana_dev.kueue import calc_nodes_diff

        kueue_resources = KueueResources(
            [KueueFlavor("flavor1", 1, "1Gi")],
            [
                KueueNode(
                    "node1", [KueueQueue("queue1", [KueueFlavor("flavor1", 1, "1Gi")])]
                )
            ],
        )
        resources_snapshot = KueueResources(
            [KueueFlavor("flavor1", 1, "1Gi")],
            [
                KueueNode(
                    "node1", [KueueQueue("queue1", [KueueFlavor("flavor1", 1, "1Gi")])]
                ),
                KueueNode(
                    "node2", [KueueQueue("queue2", [KueueFlavor("flavor1", 1, "1Gi")])]
                ),
            ],
        )

        nodes_added, nodes_removed = calc_nodes_diff(
            kueue_resources, resources_snapshot
        )

        assert nodes_added == set()
        assert nodes_removed == {"node2"}


class TestCalcQueuesDiff:
    def test_queues_added(self):
        from reana.reana_dev.kueue import calc_queues_diff

        flavor1 = KueueFlavor("flavor1", 1, "1Gi")

        kueue_resources = KueueResources(
            [flavor1],
            [
                KueueNode(
                    "node1",
                    [KueueQueue("queue1", [flavor1]), KueueQueue("queue2", [flavor1])],
                )
            ],
        )
        resources_snapshot = KueueResources(
            [flavor1], [KueueNode("node1", [KueueQueue("queue1", [flavor1])])]
        )

        queues_added, queues_modified, queues_removed = calc_queues_diff(
            kueue_resources, resources_snapshot, [], set(), set()
        )

        assert len(queues_added["node1"]) == 1
        assert queues_added["node1"][0].name == "queue2"
        assert len(queues_modified["node1"]) == 0
        assert len(queues_removed["node1"]) == 0

    def test_queues_removed(self):
        from reana.reana_dev.kueue import calc_queues_diff

        flavor1 = KueueFlavor("flavor1", 1, "1Gi")

        kueue_resources = KueueResources(
            [flavor1], [KueueNode("node1", [KueueQueue("queue1", [flavor1])])]
        )
        resources_snapshot = KueueResources(
            [flavor1],
            [
                KueueNode(
                    "node1",
                    [KueueQueue("queue1", [flavor1]), KueueQueue("queue2", [flavor1])],
                )
            ],
        )

        queues_added, queues_modified, queues_removed = calc_queues_diff(
            kueue_resources, resources_snapshot, [], set(), set()
        )

        assert len(queues_added["node1"]) == 0
        assert len(queues_modified["node1"]) == 0
        assert len(queues_removed["node1"]) == 1
        assert queues_removed["node1"][0].name == "queue2"

    def test_queues_modified_flavors_changed(self):
        from reana.reana_dev.kueue import calc_queues_diff

        flavor1 = KueueFlavor("flavor1", 1, "1Gi")
        flavor2 = KueueFlavor("flavor2", 2, "2Gi")

        kueue_resources = KueueResources(
            [flavor1, flavor2],
            [KueueNode("node1", [KueueQueue("queue1", [flavor1, flavor2])])],
        )
        resources_snapshot = KueueResources(
            [flavor1, flavor2], [KueueNode("node1", [KueueQueue("queue1", [flavor1])])]
        )

        queues_added, queues_modified, queues_removed = calc_queues_diff(
            kueue_resources, resources_snapshot, [], set(), set()
        )

        assert len(queues_added["node1"]) == 0
        assert len(queues_modified["node1"]) == 1
        assert queues_modified["node1"][0].name == "queue1"
        assert len(queues_removed["node1"]) == 0

    def test_queues_modified_due_to_modified_flavor(self):
        from reana.reana_dev.kueue import calc_queues_diff

        flavor1_old = KueueFlavor("flavor1", 1, "1Gi")
        flavor1_new = KueueFlavor("flavor1", 2, "2Gi")

        kueue_resources = KueueResources(
            [flavor1_new], [KueueNode("node1", [KueueQueue("queue1", [flavor1_new])])]
        )
        resources_snapshot = KueueResources(
            [flavor1_old], [KueueNode("node1", [KueueQueue("queue1", [flavor1_old])])]
        )

        # flavor1 is modified
        queues_added, queues_modified, queues_removed = calc_queues_diff(
            kueue_resources, resources_snapshot, [flavor1_new], set(), set()
        )

        assert len(queues_added["node1"]) == 0
        assert len(queues_modified["node1"]) == 1
        assert queues_modified["node1"][0].name == "queue1"
        assert len(queues_removed["node1"]) == 0

    def test_queues_modified_due_to_removed_flavor(self):
        from reana.reana_dev.kueue import calc_queues_diff

        flavor1 = KueueFlavor("flavor1", 1, "1Gi")
        flavor2 = KueueFlavor("flavor2", 2, "2Gi")

        kueue_resources = KueueResources(
            [flavor1], [KueueNode("node1", [KueueQueue("queue1", [flavor1])])]
        )
        resources_snapshot = KueueResources(
            [flavor1, flavor2], [KueueNode("node1", [KueueQueue("queue1", [flavor1])])]
        )

        # flavor2 is removed and queue1 uses it
        queues_added, queues_modified, queues_removed = calc_queues_diff(
            kueue_resources, resources_snapshot, [], {flavor2}, set()
        )

        # Queue should not be modified if it doesn't use the removed flavor
        assert len(queues_added["node1"]) == 0
        assert len(queues_modified["node1"]) == 0
        assert len(queues_removed["node1"]) == 0

    def test_skip_removed_nodes(self):
        from reana.reana_dev.kueue import calc_queues_diff

        flavor1 = KueueFlavor("flavor1", 1, "1Gi")

        kueue_resources = KueueResources(
            [flavor1], [KueueNode("node1", [KueueQueue("queue1", [flavor1])])]
        )
        resources_snapshot = KueueResources(
            [flavor1],
            [
                KueueNode("node1", [KueueQueue("queue1", [flavor1])]),
                KueueNode("node2", [KueueQueue("queue2", [flavor1])]),
            ],
        )

        # node2 is being removed
        queues_added, queues_modified, queues_removed = calc_queues_diff(
            kueue_resources, resources_snapshot, [], set(), {"node2"}
        )

        # node2 should be skipped, so only node1 should be in the results
        assert "node1" in queues_added
        assert "node2" not in queues_added
        assert "node1" in queues_modified
        assert "node2" not in queues_modified
        assert "node1" in queues_removed
        assert "node2" not in queues_removed


class TestGetAvailableRemotesStr:
    @patch("reana.reana_dev.kueue.get_remotes")
    def test_with_remotes(self, mock_get_remotes):
        from reana.reana_dev.kueue import get_available_remotes_str

        mock_get_remotes.return_value = ["remote1", "remote2", "remote3"]
        result = get_available_remotes_str()
        assert result == "remote1,remote2,remote3"

    @patch("reana.reana_dev.kueue.get_remotes")
    def test_without_remotes(self, mock_get_remotes):
        from reana.reana_dev.kueue import get_available_remotes_str

        mock_get_remotes.return_value = []
        result = get_available_remotes_str()
        assert "no remotes available" in result
        assert "kubeconfig.yaml" in result


class TestGetFilesInCurrentDir:
    @patch("reana.reana_dev.kueue.os.listdir")
    def test_get_files_in_current_dir(self, mock_listdir):
        from reana.reana_dev.kueue import get_files_in_current_dir

        mock_listdir.return_value = ["file1.txt", "file2.yaml", "dir1"]
        result = get_files_in_current_dir()
        assert result == ["file1.txt", "file2.yaml", "dir1"]


class TestGetRemotes:
    @patch("reana.reana_dev.kueue.get_files_in_current_dir")
    def test_get_remotes(self, mock_get_files_in_current_dir):
        from reana.reana_dev.kueue import get_remotes

        mock_get_files_in_current_dir.return_value = [
            "remote1-kubeconfig.yaml",
            "remote2-kubeconfig.yaml",
            "my-cluster-kubeconfig.yaml",
        ]
        result = get_remotes()
        assert result == ["remote1", "remote2", "my-cluster"]

    @patch("reana.reana_dev.kueue.get_files_in_current_dir")
    def test_get_remotes_empty(self, mock_get_files_in_current_dir):
        from reana.reana_dev.kueue import get_remotes

        mock_get_files_in_current_dir.return_value = []
        result = get_remotes()
        assert result == []


class TestGetResourcesFiles:
    @patch("reana.reana_dev.kueue.get_files_in_current_dir")
    def test_get_resources_files(self, mock_get_files):
        from reana.reana_dev.kueue import get_resources_files

        mock_get_files.return_value = [
            "queue1-resources.yaml",
            "queue2-resources.yaml",
            "other-file.yaml",
            "test.txt",
        ]
        result = get_resources_files()
        assert result == ["queue1-resources.yaml", "queue2-resources.yaml"]

    @patch("reana.reana_dev.kueue.get_files_in_current_dir")
    def test_get_resources_files_empty(self, mock_get_files):
        from reana.reana_dev.kueue import get_resources_files

        mock_get_files.return_value = ["file1.txt", "file2.yaml"]
        result = get_resources_files()
        assert result == []


class TestEnsureKubeconfigExists:
    @patch("reana.reana_dev.kueue.os.path.exists")
    def test_kubeconfig_exists(self, mock_exists):
        from reana.reana_dev.kueue import ensure_kubeconfig_exists

        mock_exists.return_value = True
        # Should not raise an exception
        ensure_kubeconfig_exists("test-kubeconfig.yaml")

    @patch("reana.reana_dev.kueue.os.path.exists")
    def test_kubeconfig_does_not_exist(self, mock_exists):
        from reana.reana_dev.kueue import ensure_kubeconfig_exists
        from click import ClickException

        mock_exists.return_value = False
        with pytest.raises(ClickException, match="does not exist"):
            ensure_kubeconfig_exists("test-kubeconfig.yaml")


class TestKueueFlavorEdgeCases:
    def test_flavor_with_large_memory(self):
        flavor = KueueFlavor("large", 64, "1024Ti")
        assert flavor.name == "large"
        assert flavor.cpu == "64"
        assert flavor.memory == "1024Ti"

    def test_flavor_with_string_cpu(self):
        flavor = KueueFlavor("test", "8", "16Gi")
        assert flavor.cpu == "8"

    def test_flavor_with_whitespace(self):
        flavor = KueueFlavor("  test  ", "  4  ", "  8Gi  ")
        assert flavor.name == "test"
        assert flavor.cpu == "4"
        assert flavor.memory == "8Gi"


class TestKueueQueueEdgeCases:
    def test_queue_with_multiple_flavors(self):
        flavors = [
            KueueFlavor("flavor1", 1, "1Gi"),
            KueueFlavor("flavor2", 2, "2Gi"),
            KueueFlavor("flavor3", 4, "4Gi"),
        ]
        queue = KueueQueue("multi-flavor-queue", flavors)
        assert queue.name == "multi-flavor-queue"
        assert len(queue.flavors) == 3

    def test_queue_equality_with_different_flavor_order(self):
        flavor1 = KueueFlavor("flavor1", 1, "1Gi")
        flavor2 = KueueFlavor("flavor2", 2, "2Gi")

        queue1 = KueueQueue("test", [flavor1, flavor2])
        queue2 = KueueQueue("test", [flavor2, flavor1])

        # Should be equal because we use frozenset for comparison
        assert queue1 == queue2


class TestKueueNodeEdgeCases:
    def test_node_with_multiple_queues(self):
        flavor = KueueFlavor("flavor1", 1, "1Gi")
        queues = [
            KueueQueue("queue1", [flavor]),
            KueueQueue("queue2", [flavor]),
            KueueQueue("queue3", [flavor]),
        ]
        node = KueueNode("multi-queue-node", queues)
        assert node.name == "multi-queue-node"
        assert len(node.queues) == 3


class TestKueueResourcesEdgeCases:
    def test_resources_with_multiple_nodes_and_flavors(self):
        flavors = [
            KueueFlavor("flavor1", 1, "1Gi"),
            KueueFlavor("flavor2", 2, "2Gi"),
            KueueFlavor("flavor3", 4, "4Gi"),
        ]
        nodes = [
            KueueNode("node1", [KueueQueue("queue1", [flavors[0]])]),
            KueueNode("node2", [KueueQueue("queue2", [flavors[1]])]),
            KueueNode("node3", [KueueQueue("queue3", [flavors[2]])]),
        ]
        resources = KueueResources(flavors, nodes)
        assert len(resources.flavors) == 3
        assert len(resources.nodes) == 3

    def test_get_node_returns_none_for_nonexistent(self):
        flavor = KueueFlavor("flavor1", 1, "1Gi")
        node = KueueNode("node1", [KueueQueue("queue1", [flavor])])
        resources = KueueResources([flavor], [node])

        assert resources.get_node("node1") is not None
        assert resources.get_node("nonexistent") is None
