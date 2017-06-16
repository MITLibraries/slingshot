# -*- coding: utf-8 -*-
from __future__ import absolute_import

import base64
import json
import os
import uuid
from zipfile import ZipFile

import bagit
import requests
from shapefile import Reader

from slingshot.db import engine, table, PGShapeReader
from slingshot.parsers import FGDCParser, parse
from slingshot.proj import parser
from slingshot.record import MitRecord


GEOM_TYPES = {
    1: 'POINT',
    3: 'LINESTRING',
    5: 'POLYGON',
    8: 'MULTIPOINT',
}


def unpack_zip(source, destination):
    with ZipFile(source) as zf:
        if not any([m.lower().endswith('.shp') for m in zf.namelist()]):
            raise "Only shapefiles are currently supported"
        for f in [m for m in zf.namelist() if not m.endswith('/')]:
            f_dest = os.path.join(destination, os.path.basename(f))
            with open(f_dest, 'wb') as fp, zf.open(f) as zp:
                while True:
                    chunk = zp.read(8192)
                    if not chunk:
                        break
                    fp.write(chunk)


def create_record(bag, public, secure, **kwargs):
    r = parse(bag.fgdc, FGDCParser)
    r.update(**kwargs)
    record = MitRecord(solr_geom=(r['_bbox_w'], r['_bbox_e'], r['_bbox_n'],
                                  r['_bbox_s']), **r)
    gs = public if record.dc_rights_s == 'Public' else secure
    gs = gs.rstrip('/')
    refs = {
        'http://www.opengis.net/def/serviceType/ogc/wms': '{}/wms'.format(gs),
        'http://www.opengis.net/def/serviceType/ogc/wfs': '{}/wfs'.format(gs),
    }
    record.dct_references_s = refs
    return record


def register_layer(layer_name, geoserver, workspace, datastore, auth=None):
    url = '{}/rest/workspaces/{}/datastores/{}/featuretypes'.format(
        geoserver.rstrip('/'), workspace, datastore)
    data = '<featureType><name>{}</name></featureType>'.format(layer_name)
    r = requests.post(url, auth=auth, headers={'Content-type': 'text/xml'},
                      data=data)
    r.raise_for_status()


def make_uuid(value, namespace='mit.edu'):
    try:
        ns = uuid.uuid5(uuid.NAMESPACE_DNS, namespace)
        uid = uuid.uuid5(ns, value)
    except UnicodeDecodeError:  # pragma: no cover
        # Python 2 requires a byte string for the second argument.
        # Python 3 requires a unicode string for the second argument.
        value, namespace = [bytearray(s, 'utf-8') for s in (value, namespace)]
        ns = uuid.uuid5(uuid.NAMESPACE_DNS, namespace)
        uid = uuid.uuid5(ns, value)
    return uid


def make_slug(name):
    uid = make_uuid(name)
    b32 = base64.b32encode(uid.bytes[:8])
    return 'mit-' + b32.decode('ascii').rstrip('=').lower()


class Solr(object):
    def __init__(self, url, auth=None):
        self.url = url.rstrip('/')
        self.session = requests.Session()
        self.session.auth = auth

    def add(self, record):
        url = self.url + '/update/json/docs'
        r = self.session.post(url, json=record)
        r.raise_for_status()

    def delete(self, query='dct_provenance_s:MIT'):
        url = self.url + '/update'
        r = self.session.post(url, json={'delete': {'query': query}})
        r.raise_for_status()

    def commit(self):
        url = self.url + '/update'
        r = self.session.post(url, json={'commit': {}})
        r.raise_for_status()


class GeoBag(object):
    def __init__(self, bag):
        self.bag = bagit.Bag(bag)
        self._record = None

    @classmethod
    def create(cls, directory):
        bagit.make_bag(directory)
        return cls(directory)

    def is_public(self):
        return self.record.get('dc_rights_s', '').lower() == 'public'

    @property
    def payload_dir(self):
        return os.path.join(str(self.bag), 'data')

    @property
    def name(self):
        return os.path.splitext(os.path.basename(self.shp))[0]

    @property
    def record(self):
        if self._record is None:
            rec = os.path.join(self.payload_dir, 'gbl_record.json')
            with open(rec) as fp:
                self._record = json.load(fp)
        return self._record

    @record.setter
    def record(self, value):
        path = os.path.join(self.payload_dir, 'gbl_record.json')
        s = json.dumps(value)
        if not isinstance(s, bytes):
            s = s.encode('utf-8')
        with open(path, 'wb') as fp:
            fp.write(s)
        self._record = value

    @property
    def fgdc(self):
        return self._file_by_ext('.xml')

    @property
    def shp(self):
        return self._file_by_ext('.shp')

    @property
    def prj(self):
        return self._file_by_ext('.prj')

    @property
    def cst(self):
        return self._file_by_ext('.cst')

    def save(self):
        self.bag.save(manifests=True)

    def is_valid(self):
        return self.bag.is_valid()

    def _file_by_ext(self, ext):
        fnames = [f for f in self.bag.payload_files()
                  if f.lower().endswith(ext.lower())]
        if len(fnames) > 1:
            raise Exception('Multiple files with extension {}'.format(ext))
        elif not fnames:
            raise Exception('Could not find file with extension {}'
                            .format(ext))
        return os.path.join(str(self.bag), fnames.pop())


def get_srid(prj):
    """Retrieve the SRID from the provided prj file.

    Takes the path to a .prj file. It will attempt to extract SRID
    and return as an int.
    """
    with open(prj) as fp:
        wkt = fp.read()
    res = parser.parse(wkt)
    if wkt.startswith('PROJCS'):
        srid = res.select('projcs > authority > code *')[0]
    elif wkt.startswith('GEOGCS'):
        srid = res.select('geogcs > authority > code *')[0]
    else:
        raise Exception('Cannot retrieve SRID')
    return int(srid.strip('"'))


def load_layer(bag):
    """Load the shapefile into PostGIS."""
    srid = get_srid(bag.prj)
    try:
        with open(bag.cst) as fp:
            encoding = fp.read().strip()
    except:
        encoding = 'UTF-8'
    with ShapeReader(bag.shp) as sf:
        geom_type = GEOM_TYPES[sf.shapeType]
        fields = sf.fields[1:]
        t = table(bag.name, geom_type, srid, fields)
        if t.exists():
            raise Exception('Table {} already exists'.format(bag.name))
        t.create()
        try:
            with engine().begin() as conn:
                reader = PGShapeReader(sf, srid, encoding)
                cursor = conn.connection.cursor()
                cursor.copy_from(reader, '"{}"'.format(bag.name))
            with engine().connect() as conn:
                conn.execute('CREATE INDEX "idx_{}_geom" ON "{}" USING GIST '
                             '(geom)'.format(bag.name, bag.name))
        except:
            t.drop()
            raise


class ShapeReader(Reader):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.close()

    def close(self):
        if self.shp:
            self.shp.close()
        if self.shx:
            self.shx.close()
        if self.dbf:
            self.dbf.close()
