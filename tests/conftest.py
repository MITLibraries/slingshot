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
