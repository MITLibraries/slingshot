import base64
import os
import uuid
from zipfile import ZipFile

import attr
import boto3
import requests

from slingshot import PUBLIC_WORKSPACE, RESTRICTED_WORKSPACE, DATASTORE
from slingshot.parsers import FGDCParser, parse
from slingshot.record import Record
from slingshot.s3 import S3IO


SUPPORTED_EXT = ('.shp', '.tif', '.tiff')


def unpack_zip(src_bucket, key, dest_bucket, endpoint=None):
    """Extract contents of s3://<src_bucket>/<key> into destination bucket.

    The uploaded zipfile contains both metadata and data and the structure
    of this file can be unpredictable. This will extract the files of the
    archive and write them to the destination bucket using the base name of
    the uploaded file as a key prefix. Any subdirectories within the
    uploaded zipfile are removed leaving a flattened structure in the new
    object.
    """
    s3 = boto3.resource('s3', endpoint_url=endpoint)
    name = os.path.splitext(key)[0]
    obj = S3IO(s3.Object(src_bucket, key))
    bucket = s3.Bucket(dest_bucket)
    with ZipFile(obj) as zf:
        for f in [m for m in zf.infolist() if not m.is_dir()]:
            dest = os.path.join(name, os.path.basename(f.filename))
            with zf.open(f) as fp:
                bucket.put_object(Key=dest, Body=fp)
    return dest_bucket, name


def create_record(layer, geoserver):
    """Create a :class:`slingshot.record.Record` from the given layer.

    This will create a record from the layer's FGDC file. The geoserver
    param should be the root URL of the GeoServer instance.
    """
    geoserver = geoserver.rstrip("/")
    r = parse(layer.fgdc, FGDCParser)
    record = Record(**{k: v for k, v in r.items() if not k.startswith('_')})
    workspace = PUBLIC_WORKSPACE if record.dc_rights_s == "Public" else \
        RESTRICTED_WORKSPACE
    refs = {
        'http://www.opengis.net/def/serviceType/ogc/wms':
            '{}/wms'.format(geoserver),
        'http://www.opengis.net/def/serviceType/ogc/wfs':
            '{}/wfs'.format(geoserver),
    }
    geom = "ENVELOPE({}, {}, {}, {})".format(r['_bbox_w'], r['_bbox_e'],
                                             r['_bbox_n'], r['_bbox_s'])
    record = attr.evolve(record, dc_type_s='Dataset',
                         dc_format_s=layer.format,
                         layer_id_s='{}:{}'.format(workspace, layer.name),
                         solr_geom=geom,
                         layer_slug_s=make_slug(layer.name),
                         dct_references_s=refs)
    return record


class GeoServer:
    def __init__(self, url, auth=None):
        self.url = "{}/rest".format(url.rstrip("/"))
        self.auth = auth
        self.session = requests.Session()
        self.session.auth = auth

    def post(self, path, **kwargs):
        """Make a post request to the GeoServer instance.

        Note the use of ``stream=False`` here. This ensures the session pool
        still gets used even if the response is not fully read. This
        shouldn't be a problem as none of the responses received here will be
        very large.
        """
        url = "{}/{}".format(self.url, path.lstrip("/"))
        r = self.session.post(url, stream=False, **kwargs)
        r.raise_for_status()
        return r

    def add(self, layer, s3_alias="s3"):
        """Add the layer to GeoServer.

        In the case of of a Shapefile, the layer should already exist in the
        PostGIS database. In the case of a GeoTiff, the file should already
        exist in S3.
        """
        if layer.format == 'Shapefile':
            self._add_feature(layer)
        elif layer.format == 'GeoTiff':
            self._add_coverage(layer, s3_alias)
        else:
            raise Exception("Unknown format")

    def _add_coverage(self, layer, s3_alias):
        workspace = PUBLIC_WORKSPACE if layer.is_public() else \
            RESTRICTED_WORKSPACE
        data = {
            "coverageStore": {
                "name": layer.name,
                "type": "S3GeoTiff",
                "enabled": True,
                "url": "{}://{}/{}".format(s3_alias, layer.bucket, layer.tif),
                "workspace": {"name": workspace},
            }
        }
        url = "/workspaces/{}/coveragestores".format(workspace)
        self.post(url, json=data)
        data = {
            "coverage": {
                "enabled": True,
                "name": layer.name,
                "nativeName": layer.name,
                "nativeFormat": "S3GeoTiff",
                "defaultInterpolationMethod": "nearest neighbor",
                "parameters": {
                    "entry": [
                        {"string": ["SUGGESTED_TILE_SIZE", "512,512"]},
                        {"string": ["AwsRegion", "US_EAST_1"]},
                    ]
                }
            }
        }
        url = "/workspaces/{}/coveragestores/{}/coverages".format(workspace,
                                                                  layer.name)
        self.post(url, json=data)

    def _add_feature(self, layer):
        workspace = PUBLIC_WORKSPACE if layer.is_public() else \
            RESTRICTED_WORKSPACE
        data = {"featureType": {"name": layer.name}}
        url = "/workspaces/{}/datastores/{}/featuretypes".format(workspace,
                                                                 DATASTORE)
        self.post(url, json=data)


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

    def post(self, path, **kwargs):
        url = "{}/{}".format(self.url, path)
        r = self.session.post(url, stream=False, **kwargs)
        r.raise_for_status()

    def add(self, record):
        self.post('update/json/docs', json=record)

    def delete(self, query='dct_provenance_s:MIT'):
        self.post('update', json={'delete': {'query': query}})

    def commit(self):
        self.post('update', json={'commit': {}})
