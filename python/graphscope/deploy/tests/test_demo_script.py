#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2020 Alibaba Group Holding Limited. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import logging
import os
import random
import string
import subprocess
import sys

import pytest

import graphscope
from graphscope.dataset.ldbc import load_ldbc
from graphscope.dataset.modern_graph import load_modern_graph
from graphscope.framework.loader import Loader

logger = logging.getLogger("graphscope")


@pytest.fixture
def data_dir():
    return "/testingdata/ldbc_sample"


@pytest.fixture
def modern_graph_data_dir():
    return "/testingdata/modern_graph"


def get_gs_image_on_ci_env():
    if "CI" in os.environ and "GS_IMAGE" in os.environ:
        return os.environ["GS_IMAGE"], True
    else:
        return "", False


def test_demo(data_dir):
    image, ci = get_gs_image_on_ci_env()
    if ci:
        sess = graphscope.session(
            show_log=True,
            num_workers=1,
            k8s_gs_image=image,
        )
    else:
        sess = graphscope.session(
            show_log=True,
            num_workers=1,
        )
    graph = load_ldbc(sess, data_dir)

    # Interactive engine
    interactive = sess.gremlin(graph)
    sub_graph = interactive.subgraph(  # noqa: F841
        'g.V().hasLabel("person").outE("knows")'
    )

    # Analytical engine
    # project the projected graph to simple graph.
    simple_g = sub_graph.project_to_simple(v_label="person", e_label="knows")

    pr_result = graphscope.pagerank(simple_g, delta=0.8)
    tc_result = graphscope.triangles(simple_g)

    # add the PageRank and triangle-counting results as new columns to the property graph
    # FIXME: Add column to sub_graph
    sub_graph.add_column(pr_result, {"Ranking": "r"})
    sub_graph.add_column(tc_result, {"TC": "r"})

    # GNN engine
    sess.close()


def test_demo_distribute(data_dir, modern_graph_data_dir):
    image, ci = get_gs_image_on_ci_env()
    if ci:
        sess = graphscope.session(
            show_log=True,
            num_workers=2,
            k8s_gs_image=image,
        )
    else:
        sess = graphscope.session(
            show_log=True,
            num_workers=2,
        )

    graph = load_ldbc(sess, data_dir)

    # Interactive engine
    interactive = sess.gremlin(graph)
    sub_graph = interactive.subgraph(  # noqa: F841
        'g.V().hasLabel("person").outE("knows")'
    )
    person_count = (
        interactive.execute(
            'g.V().hasLabel("person").outE("knows").bothV().dedup().count()'
        )
        .all()
        .result()[0]
    )
    knows_count = (
        interactive.execute('g.V().hasLabel("person").outE("knows").count()')
        .all()
        .result()[0]
    )
    interactive2 = sess.gremlin(sub_graph)
    sub_person_count = interactive2.execute("g.V().count()").all().result()[0]
    sub_knows_count = interactive2.execute("g.E().count()").all().result()[0]
    assert person_count == sub_person_count
    assert knows_count == sub_knows_count

    # Analytical engine
    # project the projected graph to simple graph.
    simple_g = sub_graph.project_to_simple(v_label="person", e_label="knows")

    pr_result = graphscope.pagerank(simple_g, delta=0.8)
    tc_result = graphscope.triangles(simple_g)

    # add the PageRank and triangle-counting results as new columns to the property graph
    # FIXME: Add column to sub_graph
    sub_graph.add_column(pr_result, {"Ranking": "r"})
    sub_graph.add_column(tc_result, {"TC": "r"})

    # test subgraph on modern graph
    mgraph = load_modern_graph(sess, modern_graph_data_dir)

    # Interactive engine
    minteractive = sess.gremlin(mgraph)
    msub_graph = minteractive.subgraph(  # noqa: F841
        'g.V().hasLabel("person").outE("knows")'
    )
    person_count = (
        minteractive.execute(
            'g.V().hasLabel("person").outE("knows").bothV().dedup().count()'
        )
        .all()
        .result()[0]
    )
    msub_interactive = sess.gremlin(msub_graph)
    sub_person_count = msub_interactive.execute("g.V().count()").all().result()[0]
    assert person_count == sub_person_count

    # GNN engine
    sess.close()


def test_multiple_session(data_dir):
    namespace = "gs-multi-" + "".join(
        [random.choice(string.ascii_lowercase) for _ in range(6)]
    )

    image, ci = get_gs_image_on_ci_env()
    if ci:
        sess = graphscope.session(
            show_log=True,
            k8s_namespace=namespace,
            num_workers=2,
            k8s_gs_image=image,
        )
    else:
        sess = graphscope.session(
            show_log=True,
            k8s_namespace=namespace,
            num_workers=2,
        )
    info = sess.info
    assert info["status"] == "active"
    assert info["type"] == "k8s"
    assert len(info["engine_hosts"].split(",")) == 2

    if ci:
        sess2 = graphscope.session(
            show_log=True,
            k8s_namespace=namespace,
            num_workers=2,
            k8s_gs_image=image,
        )
    else:
        sess2 = graphscope.session(
            show_log=True,
            k8s_namespace=namespace,
            num_workers=2,
        )
    info = sess2.info
    assert info["status"] == "active"
    assert info["type"] == "k8s"
    assert len(info["engine_hosts"].split(",")) == 2

    sess2.close()
    sess.close()


def test_load_modern_graph(modern_graph_data_dir):
    image, ci = get_gs_image_on_ci_env()
    if ci:
        sess = graphscope.session(
            show_log=True,
            num_workers=1,
            k8s_gs_image=image,
        )
    else:
        sess = graphscope.session(
            show_log=True,
            num_workers=1,
        )
    graph = load_modern_graph(sess, modern_graph_data_dir)
    interactive = sess.gremlin(graph)
    queries = [
        "g.V().has('name','marko').count()",
        "g.V().has('person','name','marko').count()",
        "g.V().has('person','name','marko').outE('created').count()",
        "g.V().has('person','name','marko').outE('created').inV().count()",
        "g.V().has('person','name','marko').out('created').count()",
        "g.V().has('person','name','marko').out('created').values('name').count()",
    ]
    for q in queries:
        result = interactive.execute(q).all().result()[0]
        assert result == 1
