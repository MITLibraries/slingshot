# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import shutil
import tempfile

import pytest


@pytest.yield_fixture(scope="session", autouse=True)
def reset_temp_dir():
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    tmp = tempfile.mkdtemp(dir=cur_dir)
    tempfile.tempdir = tmp
    yield
    if os.path.isdir(tmp):
        shutil.rmtree(tmp)


@pytest.fixture
def shapefile():
    return _data_file('fixtures/bermuda.zip')


@pytest.fixture
def shapefile_unpacked():
    d = os.path.join(tempfile.mkdtemp(), 'bermuda')
    b = _data_file('fixtures/bermuda_unpacked')
    shutil.copytree(b, d)
    return d


@pytest.fixture
def no_xml():
    return _data_file('fixtures/no_xml.zip')


@pytest.fixture
def bag():
    d = os.path.join(tempfile.mkdtemp(), 'bermuda')
    b = _data_file('fixtures/bermuda')
    shutil.copytree(b, d)
    return d


@pytest.fixture
def bags_dir(bag):
    return os.path.dirname(bag)


@pytest.fixture
def prj_4326():
    return _data_file('fixtures/4326.prj')


@pytest.fixture
def prj_2249():
    return _data_file('fixtures/2249.prj')


@pytest.fixture
def fgdc():
    return _data_file('fixtures/bermuda/data/bermuda.xml')


def _data_file(name):
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(cur_dir, name)
