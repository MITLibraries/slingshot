# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import tempfile
from zipfile import ZipFile

from mock import patch
import pytest
import requests
import requests_mock

from slingshot.app import (temp_archive, submit, make_uuid, write_fgdc,
                           prep_bag, uploadable, flatten_zip, make_bag_dir)


@pytest.fixture
def upload_dir():
    return tempfile.mkdtemp()


def test_make_bag_dir_creates_directory(shapefile, upload_dir):
    make_bag_dir(shapefile, upload_dir)
    assert os.path.isdir(os.path.join(upload_dir, 'SDE_DATA_BD_A8GNS_2003'))


def test_make_bag_dir_returns_dir_name(shapefile, upload_dir):
    assert make_bag_dir(shapefile, upload_dir) == \
        os.path.join(upload_dir, 'SDE_DATA_BD_A8GNS_2003')


def test_prep_bag_creates_fgdc_in_bag_dir(shapefile, upload_dir):
    prep_bag(shapefile, upload_dir)
    assert 'SDE_DATA_BD_A8GNS_2003.xml' in os.listdir(upload_dir)


def test_prep_bag_creates_zip_package_in_bag_dir(shapefile, upload_dir):
    prep_bag(shapefile, upload_dir)
    assert 'SDE_DATA_BD_A8GNS_2003.zip' in os.listdir(upload_dir)


def test_write_fgdc_writes_fgdc(shapefile, upload_dir):
    write_fgdc(shapefile, os.path.join(upload_dir, 'test.xml'))
    assert os.path.isfile(os.path.join(upload_dir, 'test.xml'))


def test_flatten_zip_moves_all_members_to_top_level(shapefile):
    with tempfile.TemporaryFile() as zf:
        flatten_zip(shapefile, zf)
        arx = ZipFile(zf)
        assert 'SDE_DATA_BD_A8GNS_2003.cst' in arx.namelist()


def test_uploadable_returns_layers_not_uploaded(layers_dir, upload_dir):
    assert list(uploadable(layers_dir, upload_dir)) == \
        ['SDE_DATA_BD_A8GNS_2003.zip']


def test_tmp_archive_creates_archive(layer):
    name = os.path.join(tempfile.mkdtemp(), 'grayscale')
    with temp_archive(layer, name) as arxiv:
        assert os.path.isfile(arxiv)


def test_tmp_archive_removes_archive(layer):
    name = os.path.join(tempfile.mkdtemp(), 'grayscale')
    with temp_archive(layer, name) as arxiv:
        pass
    assert not os.path.exists(arxiv)


def test_submit_posts_archived_bag(zipped_bag):
    with requests_mock.Mocker() as m:
        m.post('http://localhost')
        submit(zipped_bag, 'http://localhost')
    assert m.request_history[0].method == 'POST'


def test_submit_raises_error_for_failed_post(zipped_bag):
    with requests_mock.Mocker() as m:
        m.post('http://localhost', status_code=500)
        with pytest.raises(requests.HTTPError):
            submit(zipped_bag, 'http://localhost')


def test_submit_uses_authentication(zipped_bag):
    with requests_mock.Mocker() as m:
        m.post('http://localhost')
        submit(zipped_bag, 'http://localhost', ('foo', 'bar'))
    assert m.request_history[0].headers['Authorization'] == \
        'Basic Zm9vOmJhcg=='


def test_make_uuid_creates_uuid_string():
    assert make_uuid('grayscale', 'arrowsmith.mit.edu') == \
        'aabfaa4e-15a2-51b5-a684-46c530cb0263'


def test_make_uuid_works_with_unicode_values():
    assert make_uuid('grayscale', u'arrowsmith.mit.edu') == \
        'aabfaa4e-15a2-51b5-a684-46c530cb0263'
