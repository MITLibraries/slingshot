# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import tempfile

import pytest
import requests
import requests_mock

from slingshot.app import copy_dir, temp_archive, submit, make_uuid, sub_dirs


def test_copy_dir_returns_new_path(layer):
    dest = tempfile.mkdtemp()
    assert copy_dir(layer, dest) == os.path.join(dest, 'grayscale')


def test_copy_dir_copies_directory_to_new_location(layer):
    dest = tempfile.mkdtemp()
    copied = copy_dir(layer, dest)
    assert os.path.isdir(copied)


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


def test_sub_dirs_returns_list_of_sub_directories():
    d = tempfile.mkdtemp()
    os.mkdir(os.path.join(d, 'foo'))
    os.mkdir(os.path.join(d, 'bar'))
    dirs = sub_dirs(d)
    assert all(x in dirs for x in ['foo', 'bar'])


def test_sub_dirs_does_not_return_files():
    d = tempfile.mkdtemp()
    os.mkdir(os.path.join(d, 'foo'))
    tempfile.NamedTemporaryFile(dir=d, delete=False).close()
    assert sub_dirs(d) == ['foo']
