# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os.path
import tempfile

from click.testing import CliRunner
import mock
import pytest
import requests_mock

from slingshot.cli import main


@pytest.fixture
def runner():
    return CliRunner()


def test_run_submits_bags(runner, layers_dir):
    with requests_mock.Mocker() as m:
        store = tempfile.mkdtemp()
        m.post('http://localhost')
        res = runner.invoke(main, ['run', layers_dir, store,
                                   'http://localhost'])
    assert res.exit_code == 0
    assert m.request_history[0].method == 'POST'


def test_run_leaves_bag_on_success(runner, layers_dir):
    with requests_mock.Mocker() as m:
        store = tempfile.mkdtemp()
        m.post('http://localhost')
        runner.invoke(main, ['run', layers_dir, store, 'http://localhost'])
        assert os.path.isdir(os.path.join(store, 'SDE_DATA_BD_A8GNS_2003'))


def test_run_removes_bag_on_failure(runner, layers_dir):
    with requests_mock.Mocker() as m:
        store = tempfile.mkdtemp()
        m.post('http://localhost', status_code=500)
        runner.invoke(main, ['run', layers_dir, store, 'http://localhost'])
        assert not os.path.isdir(os.path.join(store, 'SDE_DATA_BD_A8GNS_2003'))


def test_run_uses_supplied_namespace(runner, layers_dir):
    with mock.patch('slingshot.cli.submit') as m:
        store = tempfile.mkdtemp()
        runner.invoke(main, ['run', layers_dir, store, 'http://localhost',
                             '--namespace', 'foo.bar'])
    assert os.path.basename(m.call_args[0][0]) == \
        '90ebb45f-ad77-5c30-ab90-1b7e389f3398.zip'


def test_run_uses_authentication(runner, layers_dir):
    with requests_mock.Mocker() as m:
        store = tempfile.mkdtemp()
        m.post('http://localhost')
        runner.invoke(main, ['run', layers_dir, store, 'http://localhost',
                             '--username', 'foo', '--password', 'bar'])
    assert m.request_history[0].headers['Authorization'] == \
        'Basic Zm9vOmJhcg=='
