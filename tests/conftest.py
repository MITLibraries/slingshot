# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import shutil
import tempfile

import boto3
import pytest
import requests_mock
from moto import mock_s3


@pytest.yield_fixture(scope="session", autouse=True)
def tmp_dir():
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    tmp = tempfile.mkdtemp(dir=cur_dir)
    tempfile.tempdir = tmp
    yield
    if os.path.isdir(tmp):
        shutil.rmtree(tmp)


@pytest.yield_fixture
def s3():
    with mock_s3():
        client = boto3.client('s3', aws_access_key_id='foo',
                              aws_secret_access_key='bar')
        client.create_bucket(Bucket='kepler')
        yield client


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
        m.get('/failed/47458e22-8e50-5b43-ac80-b662a1077af1',
              json={'status': 'FAILED'})
        m.get('/404/47458e22-8e50-5b43-ac80-b662a1077af1', status_code=404)
        m.get('/completed/47458e22-8e50-5b43-ac80-b662a1077af1',
              json={'status': 'COMPLETED'})
        m.put(requests_mock.ANY)
        yield m


def _data_file(name):
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(cur_dir, name)
