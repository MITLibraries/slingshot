# -*- coding: utf-8 -*-
from __future__ import absolute_import
import base64
import json
import os
import shutil
import tempfile
import uuid
from zipfile import ZipFile

import bagit
from geomet import wkt
from ogre.xml import FGDCParser
import requests
from shapefile import Reader

from slingshot.db import engine, table
from slingshot.proj import parser
from slingshot.record import create_record as _create_record


GEOM_TYPES = {
    1: 'POINT',
    3: 'LINESTRING',
    5: 'POLYGON',
    8: 'MULTIPOINT',
}


def unpack_zip(source, destination):
    with ZipFile(source) as zf:
        for f in [m for m in zf.namelist() if not m.endswith('/')]:
            f_dest = os.path.join(destination, os.path.basename(f))
            with open(f_dest, 'wb') as fp:
                fp.write(zf.read(f))


def make_bag_dir(source, dest_dir, overwrite=False):
    layer = os.path.basename(source)
    layer_name = os.path.splitext(layer)[0]
    destination = os.path.join(dest_dir, layer_name)
    try:
        os.mkdir(destination)
    except OSError:
        if overwrite:
            shutil.rmtree(destination)
            os.mkdir(destination)
        else:
            raise
    return destination


def create_record(bag, public, secure, **kwargs):
    record = _create_record(bag.fgdc, FGDCParser, **kwargs)
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


def index_layer(record, solr, auth=None):
    url = '{}/update/json/docs'.format(solr.rstrip('/'))
    r = requests.post(url, json=record, auth=auth)
    r.raise_for_status()


def make_uuid(value, namespace='mit.edu'):
    try:
        ns = uuid.uuid5(uuid.NAMESPACE_DNS, namespace)
        uid = uuid.uuid5(ns, value)
    except UnicodeDecodeError:
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
        with open(path, 'wb') as fp:
            json.dump(value, fp)
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


def force_utf8(value, encoding):
    """Force a value into UTF-8.

    The value could be either a bytes object, in which case ``encoding``
    is used to decode before re-encoding in UTF-8. Otherwise, it is
    assumed to be a unicode object and is encoded as UTF-8.
    """
    if isinstance(value, bytes):
        value = value.decode(encoding)
    return value.encode('utf-8')


def prep_field(field, _type, encoding):
    """Prepare a field to be written out for PostGres COPY.

    This uses the TEXT format with the default ``\\N`` marker for NULL
    values.
    """
    if field is None:
        return r'\N'
    if _type == 'C':
        field = force_utf8(field, encoding)
        quoteable = ('\t', '\n', '\r')
        if any([s in field for s in quoteable]) or field == '\.':
            field = r'\{}'.format(field)
        return field
    return str(field)


def multiply(geometry):
    """Force a GeoJSON geometry to its Multi* counterpart.

    This allows a table to load both polygons and multipolygons, for
    example.
    """
    _type = geometry['type'].lower()
    if _type == 'polygon':
        return {
            'type': 'MultiPolygon',
            'coordinates': [geometry['coordinates']]
        }
    elif _type == 'linestring':
        return {
            'type': 'MultiLineString',
            'coordinates': [geometry['coordinates']]
        }
    return geometry


def load_layer(bag):
    """Load the shapefile into PostGIS."""
    srid = get_srid(bag.prj)
    try:
        with open(bag.cst) as fp:
            encoding = fp.read().strip()
    except:
        encoding = 'ISO-8859-1'
    sf = Reader(bag.shp)
    geom_type = GEOM_TYPES[sf.shapeType]
    fields = sf.fields[1:]
    types = [f[1] for f in fields]
    t = table(bag.name, geom_type, srid, fields, encoding)
    if t.exists():
        raise Exception('Table {} already exists'.format(bag.name))
    t.create()
    with tempfile.TemporaryFile() as fp:
        try:
            for record in sf.iterShapeRecords():
                geom = 'SRID={};{}'.format(
                        srid,
                        wkt.dumps(multiply(record.shape.__geo_interface__)))
                rec = [prep_field(f, types[i], encoding) for i, f in
                       enumerate(record.record)] + [geom]
                fp.write('\t'.join(rec) + '\n')
            with engine().begin() as conn:
                fp.flush()
                fp.seek(0)
                cursor = conn.connection.cursor()
                cursor.copy_from(fp, '"{}"'.format(bag.name))
            with engine().connect() as conn:
                conn.execute('CREATE INDEX "idx_{}_geom" ON "{}" USING GIST '
                             '(geom)'.format(bag.name, bag.name))
        except:
            t.drop()
            raise
