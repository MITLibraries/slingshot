from functools import lru_cache
import json
import os
try:
    from lxml.etree import iterparse
except ImportError:
    from xml.etree.ElementTree import iterparse

from slingshot.proj import parser
from slingshot.record import Record
from slingshot.s3 import S3IO, session


_LRU_CACHE_SIZE = 32


class S3Layer:
    """Base class for a layer stored in S3.

    A layer is a collection of files that all share the same key prefix
    in the bucket. At minimum, a layer should have an FGDC XML file and the
    necessary data files.
    """
    def __init__(self, bucket, key, endpoint=None):
        self.s3 = session().resource('s3', endpoint_url=endpoint)
        self.bucket = bucket
        self.key = key
        self.endpoint = endpoint
        self._record = None

    @property
    @lru_cache(maxsize=_LRU_CACHE_SIZE)
    def manifest(self):
        """List of S3 keys for the objects in this layer.

        The list is cached after the first access.
        """
        bucket = self.s3.Bucket(self.bucket)
        return [i.key for i in bucket.objects.filter(Prefix=self.key)
                if not i.key.endswith('/')]

    @property
    def gbl_record(self):
        """A file-like object representing the GeoBlacklight record."""
        return S3IO(self.s3.Object(self.bucket,
                                   self._file_by_ext('geoblacklight.json')))

    @property
    def fgdc(self):
        """A file-like object representing the FGDC XML.

        There can sometimes be multiple XML files in a package. This will
        try to find which one is FGDC by reading the start of the XML file
        and looking for a ``metadata`` element.
        """
        files = self._files_by_ext('.xml')
        if len(files) > 1:
            for f in files:
                obj = S3IO(self.s3.Object(self.bucket, f))
                for _, elem in iterparse(obj, events=('start',)):
                    if elem.tag.lower() == 'metadata':
                        obj.seek(0)
                        return obj
                    break
        else:
            return S3IO(self.s3.Object(self.bucket, files[0]))

    @property
    def record(self):
        """The :class:`slingshot.record.Record` for the layer."""
        if not self._record:
            self._record = Record.from_file(self.gbl_record)
        return self._record

    @record.setter
    def record(self, record):
        self._record = record
        key = os.path.join(self.key, "geoblacklight.json")
        rec = json.dumps(record.as_dict()).encode("utf-8")
        self.s3.Bucket(self.bucket).put_object(Key=key, Body=rec)

    def is_public(self):
        return self.record.dc_rights_s.lower() == 'public'

    def _files_by_ext(self, ext):
        keys = [k for k in self.manifest if k.endswith(ext)]
        if not keys:
            raise PackageError('Could not find file with extension {}'
                               .format(ext))
        return keys

    def _file_by_ext(self, ext):
        keys = self._files_by_ext(ext)
        if len(keys) > 1:
            raise PackageError('Multiple files with extension {}'.format(ext))
        return keys[0]


class GeoTiff(S3Layer):
    format = "GeoTiff"

    @property
    def name(self):
        return os.path.splitext(os.path.basename(self.tif))[0]

    @property
    def tif(self):
        try:
            return self._file_by_ext('.tif')
        except PackageError:
            return self._file_by_ext('.tiff')


class Shapefile(S3Layer):
    format = "Shapefile"

    @property
    def name(self):
        shp = self._file_by_ext('.shp')
        return os.path.splitext(os.path.basename(shp))[0]

    @property
    def shp(self):
        return S3IO(self.s3.Object(self.bucket, self._file_by_ext('.shp')))

    @property
    def shx(self):
        return S3IO(self.s3.Object(self.bucket, self._file_by_ext('.shx')))

    @property
    def dbf(self):
        return S3IO(self.s3.Object(self.bucket, self._file_by_ext('.dbf')))

    @property
    def prj(self):
        return S3IO(self.s3.Object(self.bucket, self._file_by_ext('.prj')))

    @property
    def cst(self):
        return S3IO(self.s3.Object(self.bucket, self._file_by_ext('.cst')))

    @property
    @lru_cache(maxsize=_LRU_CACHE_SIZE)
    def encoding(self):
        try:
            return self.cst.read().decode().strip()
        except PackageError:
            return "UTF-8"

    @property
    @lru_cache(maxsize=_LRU_CACHE_SIZE)
    def srid(self):
        wkt = self.prj.read().decode("utf-8")
        res = parser.parse(wkt)
        if wkt.startswith('PROJCS'):
            srid = res.select('projcs > authority > code *')[0]
        elif wkt.startswith('GEOGCS'):
            srid = res.select('geogcs > authority > code *')[0]
        else:
            raise PackageError('Cannot retrieve SRID for layer s3://{}/{}'
                               .format(self.bucket, self.key))
        return int(srid.strip('"'))


def create_layer(bucket, key, endpoint=None):
    """Create a new S3Layer object.

    Factory function that creates a new :class:`slingshot.s3.S3Layer` based
    on the given bucket and key.
    """
    s3 = session().resource('s3', endpoint_url=endpoint)
    bkt = s3.Bucket(bucket)
    for item in bkt.objects.filter(Prefix=key):
        if item.key.endswith('.shp'):
            return Shapefile(bucket, key, endpoint)
        elif item.key.endswith('.tif') or item.key.endswith('.tiff'):
            return GeoTiff(bucket, key, endpoint)
    raise PackageError("Unknown layer type for object s3://{}/{}".format(
                       bucket, key))


class PackageError(Exception):
    """Errors related to package structure."""
    pass
