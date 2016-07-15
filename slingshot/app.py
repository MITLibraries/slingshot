# -*- coding: utf-8 -*-
from __future__ import absolute_import
import contextlib
import os
import shutil
import tempfile
import uuid
from zipfile import ZipFile

import requests


class Kepler(object):
    def __init__(self, url=None, auth=None):
        if url:
            self.url = url
        self.session = requests.Session()
        self.session.auth = auth

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, url):
        self._url = url.rstrip('/')

    def status(self, layer):
        r = self.session.get('{}/{}'.format(self.url, layer),
                             headers={'Accept': 'application/json'})
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json().get('status')

    def submit_job(self, layer):
        r = self.session.put('{}/{}'.format(self.url, layer))
        r.raise_for_status()


def make_bag_dir(layer_name, destination):
    extracted = os.path.join(destination, layer_name)
    try:
        os.mkdir(extracted)
    except OSError:
        shutil.rmtree(extracted)
        os.mkdir(extracted)
    return extracted


def write_fgdc(archive, filename):
    with ZipFile(archive) as zf:
        if len([f for f in zf.namelist() if f.endswith('.xml')]) != 1:
            raise Exception("Could not find FGDC metadata.")
        for f in zf.namelist():
            if f.endswith('.xml'):
                with open(filename, 'wb') as fp:
                    fp.write(zf.read(f))
                return


def flatten_zip(archive, zipname):
    with ZipFile(archive) as zf:
        with ZipFile(zipname, 'w') as target:
            for f in [m for m in zf.namelist() if os.path.basename(m)]:
                target.writestr(os.path.basename(f), zf.read(f))


def make_uuid(value, namespace):
    try:
        ns = uuid.uuid5(uuid.NAMESPACE_DNS, namespace)
        uid = uuid.uuid5(ns, value)
    except UnicodeDecodeError:
        # Python 2 requires a byte string for the second argument.
        # Python 3 requires a unicode string for the second argument.
        value, namespace = [_bytes(s) for s in (value, namespace)]
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


def _bytes(value):
    return bytearray(value, 'utf-8')
