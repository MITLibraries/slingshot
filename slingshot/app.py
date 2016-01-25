# -*- coding: utf-8 -*-
from __future__ import absolute_import
import contextlib
import io
import os
import shutil
import tempfile
import uuid

import requests


def copy_dir(directory, destination):
    """Copy a directory to a destination directory.

    The directory will be copied to a directory with the same name
    in the destination directory. If the copy fails for any reason
    the copied directory will be removed. Returns the absolute path
    to the newly created directory.
    """
    dirname = os.path.basename(os.path.normpath(directory))
    dest = os.path.join(destination, dirname)
    try:
        shutil.copytree(directory, dest)
    except Exception as e:
        shutil.rmtree(destination, ignore_errors=True)
        raise e
    return dest


def submit(archive, url):
    r = requests.post(url, files={'file': io.open(archive, 'rb')})
    r.raise_for_status()


def make_uuid(value, namespace):
    ns = uuid.uuid5(uuid.NAMESPACE_DNS, namespace)
    uid = uuid.uuid5(ns, value)
    return str(uid)


@contextlib.contextmanager
def temp_archive(data, name):
    """Create a temporary archive that is automatically removed.

    This context manager will create a temporary ZIP archive of data
    the provided name. A `.zip` suffix will be appended to the name.
    The archive is deleted upon exiting the content manager.
    """
    tmp = tempfile.gettempdir()
    archive_name = os.path.join(tmp, name)
    root_dir = os.path.dirname(os.path.normpath(data))
    base_dir = os.path.basename(os.path.normpath(data))
    try:
        archive = shutil.make_archive(archive_name, 'zip', root_dir, base_dir)
        yield archive
    finally:
        os.remove(archive)


def sub_dirs(directory):
    return [d for d in os.listdir(directory)
            if os.path.isdir(os.path.join(directory, d))]
