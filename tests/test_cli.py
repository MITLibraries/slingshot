# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os.path
import tempfile

from click.testing import CliRunner
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
        assert os.path.isdir(os.path.join(store, 'grayscale'))


def test_run_removes_bag_on_failure(runner, layers_dir):
    with requests_mock.Mocker() as m:
        store = tempfile.mkdtemp()
        m.post('http://localhost', status_code=500)
        runner.invoke(main, ['run', layers_dir, store, 'http://localhost'])
        assert not os.path.isdir(os.path.join(store, 'grayscale'))
