# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2018 CERN.
#
# REANA is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# REANA is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# REANA; if not, write to the Free Software Foundation, Inc., 59 Temple Place,
# Suite 330, Boston, MA 02111-1307, USA.
#
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as an Intergovernmental Organization or
# submit itself to any jurisdiction.

"""REANA CLI tests."""

from __future__ import absolute_import, print_function

import os


def test_shorten_component_name():
    """Tests for shorten_component_name()."""
    from reana.cli import shorten_component_name
    for (name_long, name_short) in (
            ('', ''),
            ('reana', 'reana'),
            ('reana-job-controller', 'r-j-controller'),
    ):
        assert name_short == shorten_component_name(name_long)


def test_is_component_dockerised():
    """Tests for is_component_dockerised()."""
    from reana.cli import is_component_dockerised
    if os.environ.get('REANA_SRCDIR'):
        assert is_component_dockerised('reana-workflow-controller') is True
        assert is_component_dockerised('reana-cluster') is False


def test_select_components():
    """Tests for select_components()."""
    from reana.cli import select_components, REPO_LIST_ALL, REPO_LIST_CLUSTER
    for (input_value, output_expected) in (
            (['reana-job-controller', ], ['reana-job-controller', ]),
            (['reana-job-controller', 'reana', ],
             ['reana-job-controller', 'reana, ']),
            (['cluster', ], REPO_LIST_CLUSTER),
            (['cluster', 'reana', ], REPO_LIST_CLUSTER),
            (['all', ], REPO_LIST_ALL),
            (['all', 'reana', ], REPO_LIST_ALL),
            (['all', 'cluster', 'reana'], REPO_LIST_ALL),
    ):
        output_obtained = select_components(input_value)
        assert output_obtained.sort() == output_expected.sort()
