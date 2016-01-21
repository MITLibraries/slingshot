# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os.path
import tempfile

import pytest
import requests
import requests_mock

from slingshot.app import (copy_dir, create_bag, temp_archive, submit,
                           make_uuid,)


def test_copy_dir_returns_new_path(layer):
    dest = tempfile.mkdtemp()
    assert copy_dir(layer, dest) == os.path.join(dest, 'grayscale')


def test_copy_dir_copies_directory_to_new_location(layer):
    dest = tempfile.mkdtemp()
    copied = copy_dir(layer, dest)
    assert os.path.isdir(copied)


def test_create_bag_turns_directory_into_bag(layer):
    dest = tempfile.mkdtemp()
    create_bag(layer, dest)
    assert os.path.isfile(os.path.join(dest, 'grayscale', 'manifest-md5.txt'))


def test_create_bag_returns_path_to_bag(layer):
    dest = tempfile.mkdtemp()
    assert create_bag(layer, dest) == os.path.join(dest, 'grayscale')


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


def test_make_uuid_creates_uuid_string():
    assert make_uuid('grayscale', 'arrowsmith.mit.edu') == \
        'aabfaa4e-15a2-51b5-a684-46c530cb0263'
