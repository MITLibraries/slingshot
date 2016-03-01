# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import tempfile

from mock import patch
import pytest
import requests
import requests_mock

from slingshot.app import (temp_archive, submit, make_uuid, write_fgdc,
                           prep_bag, uploadable)


@pytest.fixture
def upload_dir():
    return tempfile.mkdtemp()


def test_prep_bag_removes_bag_dir_when_errors(shapefile, upload_dir):
    with patch('slingshot.app.write_fgdc') as mk:
        mk.side_effect = Exception()
        with pytest.raises(Exception):
            prep_bag(shapefile, upload_dir)
    assert not os.listdir(upload_dir)


def test_prep_bag_copies_zip_package_to_bag_dir(shapefile, upload_dir):
    prep_bag(shapefile, upload_dir)
    assert 'SDE_DATA_BD_A8GNS_2003.zip' in \
        os.listdir(os.path.join(upload_dir, 'SDE_DATA_BD_A8GNS_2003'))


def test_prep_bag_returns_location(shapefile, upload_dir):
    assert prep_bag(shapefile, upload_dir) == \
        os.path.join(upload_dir, 'SDE_DATA_BD_A8GNS_2003')


def test_write_fgdc_writes_fgdc(shapefile, upload_dir):
    write_fgdc(shapefile, os.path.join(upload_dir, 'test.xml'))
    assert os.path.isfile(os.path.join(upload_dir, 'test.xml'))


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
