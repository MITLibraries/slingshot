# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import tempfile

from click.testing import CliRunner
import pytest
import requests_mock

from slingshot.cli import main


@pytest.fixture
def runner():
    return CliRunner()


def test_run_submits_job(runner, layers_dir, kepler):
    store = tempfile.mkdtemp()
    res = runner.invoke(main, ['run', layers_dir, store,
                               'mock://example.com/404'])
    assert res.exit_code == 0
    assert kepler.request_history[0].method == 'GET'
    assert kepler.request_history[1].method == 'PUT'


def test_run_leaves_bag_on_success(runner, layers_dir, kepler):
    store = tempfile.mkdtemp()
    runner.invoke(main, ['run', layers_dir, store, 'mock://example.com/404'])
    bag = os.path.join(store, 'SDE_DATA_BD_A8GNS_2003/data')
    assert 'SDE_DATA_BD_A8GNS_2003.zip' in os.listdir(bag)
    assert 'SDE_DATA_BD_A8GNS_2003.xml' in os.listdir(bag)


def test_run_removes_bag_on_failure(runner, layers_dir, kepler):
    kepler.register_uri('PUT', requests_mock.ANY, status_code=500)
    store = tempfile.mkdtemp()
    res = runner.invoke(main, ['run', layers_dir, store,
                               'mock://example.com/404'])
    assert res.exit_code == 0
    assert not os.path.isdir(os.path.join(store, 'SDE_DATA_BD_A8GNS_2003'))


def test_run_uses_supplied_namespace(runner, layers_dir, kepler):
    kepler.get('/90ebb45f-ad77-5c30-ab90-1b7e389f3398', status_code=404)
    kepler.put('/90ebb45f-ad77-5c30-ab90-1b7e389f3398')
    store = tempfile.mkdtemp()
    runner.invoke(main, ['run', layers_dir, store, 'mock://example.com',
                         '--namespace', 'foo.bar'])
    assert kepler.call_count == 2
    assert kepler.request_history[0].url == \
        'mock://example.com/90ebb45f-ad77-5c30-ab90-1b7e389f3398'


def test_run_uses_authentication(runner, layers_dir, kepler):
    store = tempfile.mkdtemp()
    runner.invoke(main, ['run', layers_dir, store, 'mock://example.com/404',
                         '--username', 'foo', '--password', 'bar'])
    assert kepler.request_history[0].headers['Authorization'] == \
        'Basic Zm9vOmJhcg=='


def test_run_logs_uploaded_layers_to_stdout(runner, layers_dir, kepler):
    store = tempfile.mkdtemp()
    res = runner.invoke(main, ['run', layers_dir, store,
                               'mock://example.com/404'])
    assert 'SDE_DATA_BD_A8GNS_2003 uploaded' in res.output


def test_run_logs_failed_layers_to_stdout(runner, layers_dir, kepler):
    kepler.register_uri('PUT', requests_mock.ANY, status_code=500)
    store = tempfile.mkdtemp()
    res = runner.invoke(main, ['run', layers_dir, store,
                               'mock://example.com/404'])
    assert 'SDE_DATA_BD_A8GNS_2003 failed' in res.output


def test_run_fails_after_consecutive_failures(runner, layers_dir, kepler):
    kepler.register_uri('PUT', requests_mock.ANY, status_code=500)
    store = tempfile.mkdtemp()
    res = runner.invoke(main, ['run', layers_dir, store,
                               'mock://example.com/404', '--fail-after', 1])
    assert 'Maximum number of consecutive failures' in res.output
