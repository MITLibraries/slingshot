import base64
from datetime import datetime
import os
import threading
import uuid
from zipfile import ZipFile

import attr
import requests

from slingshot import PUBLIC_WORKSPACE, RESTRICTED_WORKSPACE, DATASTORE
from slingshot.db import load_layer
from slingshot.layer import create_layer
from slingshot.parsers import FGDCParser, parse
from slingshot.record import Record
from slingshot.s3 import S3IO, session, upload


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
    s3 = session().resource('s3', endpoint_url=endpoint)
    name = os.path.splitext(key)[0]
    obj = S3IO(s3.Object(src_bucket, key))
    client = session().client('s3', endpoint_url=endpoint)
    with ZipFile(obj) as zf:
        for f in [m for m in zf.infolist() if not m.is_dir()]:
            dest = os.path.join(name, os.path.basename(f.filename))
            with zf.open(f) as fp:
                upload(fp, dest_bucket, dest, client)
    return dest_bucket, name


def create_record(layer, geoserver):
    """Create a :class:`slingshot.record.Record` from the given layer.

    This will create a record from the layer's FGDC file. The geoserver
    param should be the root URL of the GeoServer instance.
    """
    geoserver = geoserver.rstrip("/")
    fgdc = layer.fgdc
    r = parse(fgdc, FGDCParser)
    record = Record(**{k: v for k, v in r.items() if not k.startswith('_')})
    workspace = PUBLIC_WORKSPACE if record.dc_rights_s == "Public" else \
        RESTRICTED_WORKSPACE
    refs = {
        'http://www.opengis.net/def/serviceType/ogc/wms':
            '{}/wms'.format(geoserver),
        'http://www.opengis.net/def/serviceType/ogc/wfs':
            '{}/wfs'.format(geoserver),
        'http://www.opengis.net/cat/csw/csdgm/':
            'https://{}.s3.amazonaws.com/{}'.format(fgdc.obj.bucket_name,
                                                    fgdc.obj.key),
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


def make_uuid(value, namespace='mit.edu'):
    ns = uuid.uuid5(uuid.NAMESPACE_DNS, namespace)
    return uuid.uuid5(ns, value)


def make_slug(name):
    uid = make_uuid(name)
    b32 = base64.b32encode(uid.bytes[:8])
    return 'mit-' + b32.decode('ascii').rstrip('=').lower()


class HttpSession:
    """Threadsafe requests.Session.

    This can be used more or less like the usual requests.Session. The only
    method it supports is ``request``. For example::

        session = HttpSession()
        def run():
            session.request("GET", "https://httpbin.org")

        t = threading.Thread(target=run)
        t.start()

    """
    def __init__(self):
        self._session = threading.local()

    @property
    def session(self):
        try:
            return self._session.s
        except AttributeError:
            self._session.s = requests.Session()
        return self._session.s

    def request(self, method, url, **kwargs):
        return self.session.request(method, url, **kwargs)


class HttpMethodMixin:
    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)


class GeoServer(HttpMethodMixin):
    def __init__(self, url, client, auth=None, s3_alias="s3"):
        self.url = url.rstrip("/")
        self.client = client
        self.auth = auth
        self.s3_alias = s3_alias

    def request(self, method, path, **kwargs):
        """Make a request.

        Note the use of ``stream=False`` here. This ensures the session pool
        still gets used even if the response is not fully read. This
        shouldn't be a problem as none of the responses received here will be
        very large.
        """
        kwargs = {"stream": False, "auth": self.auth, **kwargs}
        url = "{}/rest/{}".format(self.url, path.lstrip("/"))
        r = self.client.request(method, url, **kwargs)
        r.raise_for_status()
        return r

    def add(self, layer):
        """Add the layer to GeoServer.

        In the case of of a Shapefile, the layer should already exist in the
        PostGIS database. In the case of a GeoTiff, the file should already
        exist in S3.
        """
        if layer.format == 'Shapefile':
            self._add_feature(layer)
        elif layer.format == 'GeoTiff':
            self._add_coverage(layer)
        else:
            raise Exception("Unknown format")

    def _add_coverage(self, layer):
        workspace = PUBLIC_WORKSPACE if layer.is_public() else \
            RESTRICTED_WORKSPACE
        data = {
            "coverageStore": {
                "name": layer.name,
                "type": "S3GeoTiff",
                "enabled": True,
                "url": "{}://{}/{}".format(self.s3_alias, layer.bucket,
                                           layer.tif),
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


class Solr(HttpMethodMixin):
    def __init__(self, url, client, auth=None):
        self.url = url.rstrip("/")
        self.client = client
        self.auth = auth

    def request(self, method, path, **kwargs):
        kwargs = {"stream": False, "auth": self.auth, **kwargs}
        url = "{}/{}".format(self.url, path.lstrip("/"))
        r = self.client.request(method, url, **kwargs)
        r.raise_for_status()
        return r

    def add(self, record, soft_commit=True):
        params = {"softCommit": "true"} if soft_commit else None
        self.post('update/json/docs', params=params, json=record)

    def delete(self, query='dct_provenance_s:MIT'):
        self.post('update', json={'delete': {'query': query}})

    def commit(self):
        self.post('update', json={'commit': {}})


def publish_layer(bucket, key, geoserver, solr, destination, ogc_proxy,
                  s3_url=None):
    unpacked = unpack_zip(bucket, key, destination, s3_url)
    layer = create_layer(*unpacked, s3_url)
    layer.record = create_record(layer, ogc_proxy)
    layer.fgdc.obj.Acl().put(ACL="public-read")
    if layer.format == "Shapefile":
        load_layer(layer)
    geoserver.add(layer)
    solr.add(layer.record.as_dict())
    return layer.name


def publishable_layers(bucket, dynamodb):
    for page in bucket.objects.pages():
        for obj in page:
            name = os.path.splitext(obj.key)[0]
            res = dynamodb.get_item(Key={"LayerName": name})
            layer = res.get("Item")
            if layer:
                l_mod = datetime.fromisoformat(layer['LastMod'])
                if l_mod > obj.last_modified.replace(tzinfo=None):
                    # published layer is newer than uploaded layer
                    continue
            yield obj.key
