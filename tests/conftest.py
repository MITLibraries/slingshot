# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import shutil
import tempfile

import pytest
import requests_mock


@pytest.yield_fixture(scope="session", autouse=True)
def tmp_dir():
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    tmp = tempfile.mkdtemp(dir=cur_dir)
    tempfile.tempdir = tmp
    yield
    if os.path.isdir(tmp):
        shutil.rmtree(tmp)


@pytest.fixture
def layer():
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(cur_dir, 'fixtures/grayscale')


@pytest.fixture
def zipped_bag():
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(cur_dir, 'fixtures/bag.zip')


@pytest.fixture
def shapefile():
    return _data_file('fixtures/SDE_DATA_BD_A8GNS_2003.zip')


@pytest.fixture
def no_xml(shapefile):
    return _data_file('fixtures/no_xml.zip')


@pytest.fixture
def layers_dir(shapefile):
    d = tempfile.mkdtemp()
    shutil.copy2(shapefile, d)
    return d


@pytest.yield_fixture
def kepler():
    with requests_mock.Mocker() as m:
        m.register_uri('GET', '/failed/47458e22-8e50-5b43-ac80-b662a1077af1',
                       json={'status': 'FAILED'})
        m.register_uri('GET', '/404/47458e22-8e50-5b43-ac80-b662a1077af1',
                       status_code=404)
        m.register_uri('GET',
                       '/completed/47458e22-8e50-5b43-ac80-b662a1077af1',
                       json={'status': 'COMPLETED'})
        m.register_uri('PUT', requests_mock.ANY)
        yield m


def _data_file(name):
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(cur_dir, name)
