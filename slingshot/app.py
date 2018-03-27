import base64
import os
import re
import shutil
import uuid
from zipfile import ZipFile

import attr
import bagit
import requests
from shapefile import Reader

from slingshot.db import engine, table, PGShapeReader
from slingshot.parsers import FGDCParser, parse
from slingshot.proj import parser
from slingshot.record import Record


GEOM_TYPES = {
    1: 'POINT',
    3: 'LINESTRING',
    5: 'POLYGON',
    8: 'MULTIPOINT',
}

SUPPORTED_EXT = ('.shp', '.tif', '.tiff')


def unpack_zip(source, destination):
    with ZipFile(source) as zf:
        if not [f for f in zf.namelist()
                if os.path.splitext(f)[1] in SUPPORTED_EXT]:
            raise "Only Shapefiles and GeoTIFFs are currently supported."
        for f in [m for m in zf.namelist() if not m.endswith('/')]:
            f_dest = os.path.join(destination, os.path.basename(f))
            with open(f_dest, 'wb') as fp, zf.open(f) as zp:
                while True:
                    chunk = zp.read(8192)
                    if not chunk:
                        break
                    fp.write(chunk)


def create_record(bag, public, secure, workspace):
    r = parse(bag.fgdc, FGDCParser)
    record = Record(**{k: v for k,v in r.items() if not k.startswith('_')})
    gs = public if record.dc_rights_s == 'Public' else secure
    refs = {
        'http://www.opengis.net/def/serviceType/ogc/wms': '{}/wms'.format(gs),
        'http://www.opengis.net/def/serviceType/ogc/wfs': '{}/wfs'.format(gs),
    }
    geom = "ENVELOPE({}, {}, {}, {})".format(r['_bbox_w'], r['_bbox_e'],
                                             r['_bbox_n'], r['_bbox_s'])
    record = attr.evolve(record, dc_type_s='Dataset',
                         dc_format_s=bag.format,
                         layer_id_s='{}:{}'.format(workspace, bag.name),
                         solr_geom=geom,
                         layer_slug_s=make_slug(bag.name),
                         dct_references_s=refs)
    return record


def add_layer(bag, geoserver, workspace, datastore=None, tiff_store=None,
              tiff_url=None):
    if bag.format == 'Shapefile':
        handler = FeatureHandler(bag, geoserver, workspace, datastore)
    elif bag.format == 'GeoTiff':
        handler = TiffHandler(bag, geoserver, workspace, tiff_store,
                              tiff_url)
    else:
        raise Exception('Unknown bag format')
    handler.add()


class TiffHandler:
    def __init__(self, bag, geoserver, workspace, destination, tiff_url):
        self.bag = bag
        self.geoserver = geoserver
        self.workspace = workspace
        self.destination = destination
        self.tiff_url = tiff_url
        access = 'public' if bag.is_public() else 'secure'
        self.server = self.geoserver.url(access)

    def add(self):
        path = self._upload_layer(self.destination)
        url = ("{}/rest/workspaces/{}/coveragestores/{}/external.geotiff?"
               "configure=first&coverageName={}").format(self.server,
                                                         self.workspace,
                                                         self.bag.name,
                                                         self.bag.name)
        self.geoserver.put(url, data=path,
                           headers={'Content-type': 'text/plain'})
        self.bag.record \
            .dct_references_s['http://schema.org/downloadUrl'] = \
            self.tiff_url + os.path.split(self.bag.tif)[1]
        self.bag.save()

    def _upload_layer(self, destination):
        """Upload the layer somewhere Web accessible.

        This just copies the Tiff file from the NFS partition to a
        directory served by Apache.
        """
        tiff_path = shutil.copy(self.bag.tif, os.path.join(destination))
        return "file:" + tiff_path


class FeatureHandler:
    def __init__(self, bag, geoserver, workspace, datastore):
        self.bag = bag
        self.geoserver = geoserver
        self.workspace = workspace
        self.datastore = datastore
        access = 'public' if bag.is_public() else 'secure'
        self.server = self.geoserver.url(access)

    def add(self):
        data = '<featureType><name>{}</name></featureType>'.format(
            self.bag.name)
        self.geoserver.post(
            "{}/rest/workspaces/{}/datastores/{}/featuretypes".format(
                self.server, self.workspace, self.datastore),
            data=data, headers={'Content-type': 'test/xml'})


class GeoServer:
    def __init__(self, public="", secure="", auth=None):
        self.public = public
        self.secure = secure
        self.auth = auth
        self.session = requests.Session()
        self.session.auth = auth

    def post(self, url, **kwargs):
        r = self.session.post(url, **kwargs)
        r.raise_for_status()
        return r

    def put(self, url, **kwargs):
        r = self.session.put(url, **kwargs)
        r.raise_for_status()
        return r

    def url(self, access):
        return self.public if access == 'public' else self.secure


def make_uuid(value, namespace='mit.edu'):
    ns = uuid.uuid5(uuid.NAMESPACE_DNS, namespace)
    return uuid.uuid5(ns, value)


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
        self.bag = bag
        self._fgdc = None
        try:
            self.record = Record.from_file(self.gbl_record)
        except Exception:
            self.record = Record()

    def is_public(self):
        return self.record.dc_rights_s.lower() == 'public'

    @property
    def payload_dir(self):
        return os.path.join(str(self.bag), 'data')

    @property
    def gbl_record(self):
        return os.path.join(self.payload_dir, 'gbl_record.json')

    @property
    def fgdc(self):
        """Full path to FGDC file."""
        # There can sometimes be multiple XML files in a package. We will
        # try to find an FGDC file among them.
        if not self._fgdc:
            files = self._files_by_ext('.xml')
            if len(files) > 1:
                for f in files:
                    with open(f, encoding="utf-8") as fp:
                        head = fp.read(1024)
                    if re.match('\s*<metadata>', head, re.I):
                        self._fgdc = f
                        break
            else:
                self._fgdc = files[0]
        return self._fgdc

    def save(self):
        self.record.to_file(self.gbl_record)
        self.bag.save(manifests=True)

    def is_valid(self):
        return self.bag.is_valid()

    def _files_by_ext(self, ext):
        """Return list of full paths to files with given extension.

        Raises :class:`slingshot.app.MissingFile` exception when no
        file with the given extension is found.
        """
        fnames = [f for f in self.bag.payload_files()
                  if f.lower().endswith(ext.lower())]
        if not fnames:
            raise MissingFile('Could not find file with extension {}'
                              .format(ext))
        return [os.path.join(str(self.bag), name) for name in fnames]

    def _file_by_ext(self, ext):
        """Return full path to a single file with the given extension.

        Raises :class:`slingshot.app.TooManyFiles` exception when more
        than one file with the specified extension is found.
        """
        fnames = self._files_by_ext(ext)
        if len(fnames) > 1:
            raise TooManyFiles('Multiple files with extension {}'.format(ext))
        return fnames[0]


class GeoTiffBag(GeoBag):
    format = "GeoTiff"

    @property
    def name(self):
        return os.path.splitext(os.path.basename(self.tif))[0]

    @property
    def tif(self):
        try:
            return self._file_by_ext('.tif')
        except MissingFile:
            return self._file_by_ext('.tiff')


class ShapeBag(GeoBag):
    format = "Shapefile"

    @property
    def name(self):
        return os.path.splitext(os.path.basename(self.shp))[0]

    @property
    def shp(self):
        return self._file_by_ext('.shp')

    @property
    def prj(self):
        return self._file_by_ext('.prj')

    @property
    def cst(self):
        return self._file_by_ext('.cst')


def load_bag(directory):
    """Loads an existing bag."""
    b = bagit.Bag(directory)
    b_type = _bag_type(b)
    if b_type == 'Shapefile':
        return ShapeBag(b)
    elif b_type == 'GeoTiff':
        return GeoTiffBag(b)
    raise "Unsupported spatial format"


def make_bag(directory):
    """Creates a new bag out of the given directory."""
    bagit.make_bag(directory)
    return load_bag(directory)


def _bag_type(bag):
    for path, _ in bag.entries.items():
        if path.endswith('.shp'):
            return 'Shapefile'
        elif path.endswith('.tif') or path.endswith('.tiff'):
            return 'GeoTiff'


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
    except Exception:
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
        except Exception:
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


class MissingFile(Exception):
    """Required file in spatial data package is missing."""


class TooManyFiles(Exception):
    """Too many files of the same extension found in spatial data package."""
