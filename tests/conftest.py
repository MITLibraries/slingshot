# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import shutil
import tempfile

import pytest


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


def _data_file(name):
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(cur_dir, name)
