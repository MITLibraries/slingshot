# -*- coding: utf-8 -*-
from __future__ import absolute_import
import contextlib
import io
import os
import shutil
import tempfile
import uuid
from zipfile import ZipFile

import requests


def prep_bag(layer, destination):
    layer_name = os.path.splitext(os.path.basename(layer))[0]
    extracted = os.path.join(destination, layer_name)
    os.mkdir(extracted)
    try:
        write_fgdc(layer,
                   os.path.join(extracted, "%s.xml" % layer_name))
        flatten_zip(layer,
                    os.path.join(extracted, "%s.zip" % layer_name))
    except Exception as e:
        shutil.rmtree(extracted, ignore_errors=True)
        raise e
    return extracted


def write_fgdc(layer, filename):
    with ZipFile(layer) as zf:
        for f in zf.namelist():
            if f.endswith('.xml'):
                with open(filename, 'wb') as fp:
                    fp.write(zf.read(f))
                return


def flatten_zip(layer, zipname):
    with ZipFile(layer) as zf:
        with ZipFile(zipname, 'w') as target:
            for f in [m for m in zf.namelist() if os.path.basename(m)]:
                target.writestr(os.path.basename(f), zf.read(f))


def uploadable(layers, uploaded):
    loaded_dirs = [d for d in os.listdir(uploaded)
                   if os.path.isdir(os.path.join(uploaded, d))]
    for layer in [z for z in os.listdir(layers) if z.endswith('.zip')]:
        if os.path.splitext(layer)[0] not in loaded_dirs:
            yield layer


def submit(archive, url, auth=None):
    r = requests.post(url, files={'file': io.open(archive, 'rb')},
                      auth=auth)
    r.raise_for_status()


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
