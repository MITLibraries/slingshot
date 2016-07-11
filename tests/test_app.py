# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import tempfile
from zipfile import ZipFile

import pytest

from slingshot.app import (temp_archive, make_uuid, write_fgdc, flatten_zip,
                           make_bag_dir, Kepler)


@pytest.fixture
def upload_dir():
    return tempfile.mkdtemp()


def test_make_bag_dir_creates_directory(upload_dir):
    make_bag_dir('TEST_BAG', upload_dir)
    assert os.path.isdir(os.path.join(upload_dir, 'TEST_BAG'))


def test_make_bag_dir_returns_dir_name(upload_dir):
    assert make_bag_dir('TEST_BAG', upload_dir) == \
        os.path.join(upload_dir, 'TEST_BAG')


def test_write_fgdc_writes_fgdc(shapefile, upload_dir):
    write_fgdc(shapefile, os.path.join(upload_dir, 'test.xml'))
    assert os.path.isfile(os.path.join(upload_dir, 'test.xml'))


def test_write_fgdc_raises_error_when_no_xml(no_xml, upload_dir):
    with pytest.raises(Exception):
        write_fgdc(no_xml, os.path.join(upload_dir, 'test.xml'))


def test_flatten_zip_moves_all_members_to_top_level(shapefile):
    with tempfile.TemporaryFile() as zf:
        flatten_zip(shapefile, zf)
        arx = ZipFile(zf)
        assert 'SDE_DATA_BD_A8GNS_2003.cst' in arx.namelist()


def test_tmp_archive_creates_archive(layer):
    name = os.path.join(tempfile.mkdtemp(), 'grayscale')
    with temp_archive(layer, name) as arxiv:
        assert os.path.isfile(arxiv)


def test_tmp_archive_removes_archive(layer):
    name = os.path.join(tempfile.mkdtemp(), 'grayscale')
    with temp_archive(layer, name) as arxiv:
        pass
    assert not os.path.exists(arxiv)


def test_kepler_returns_status(kepler):
    k = Kepler('mock://example.com/completed/')
    assert k.status('47458e22-8e50-5b43-ac80-b662a1077af1') == 'COMPLETED'


def test_kepler_returns_no_status_when_no_layer_found(kepler):
    k = Kepler('mock://example.com/404/')
    assert k.status('47458e22-8e50-5b43-ac80-b662a1077af1') is None


def test_kepler_submits_job(kepler):
    k = Kepler('mock://example.com/')
    k.submit_job('47458e22-8e50-5b43-ac80-b662a1077af1')
    assert kepler.called


def test_kepler_uses_authentication(kepler):
    k = Kepler('mock://example.com/', ('foo', 'bar'))
    k.submit_job('47458e22-8e50-5b43-ac80-b662a1077af1')
    assert kepler.request_history[0].headers['Authorization'] == \
        'Basic Zm9vOmJhcg=='


def test_make_uuid_creates_uuid_string():
    assert make_uuid('grayscale', 'arrowsmith.mit.edu') == \
        'aabfaa4e-15a2-51b5-a684-46c530cb0263'


def test_make_uuid_works_with_unicode_values():
    assert make_uuid('grayscale', u'arrowsmith.mit.edu') == \
        'aabfaa4e-15a2-51b5-a684-46c530cb0263'
