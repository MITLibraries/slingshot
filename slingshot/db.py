import io
import re

from geoalchemy2 import Geometry
from geomet import wkt
from shapefile import Reader
from sqlalchemy import (
    Boolean,
    Column,
    create_engine,
    Date,
    Float,
    Integer,
    MetaData,
    Table,
    Text,
)

from slingshot import S3_BUFFER_SIZE


GEOM_TYPES = {
    1: 'POINT',
    3: 'LINESTRING',
    5: 'POLYGON',
    8: 'MULTIPOINT',
}

quote = re.compile(r'(\t|\n|\r|\\.)')


class Engine:
    _engine = None

    def __call__(self):
        return self._engine

    def configure(self, url, schema=None):
        self._engine = self._engine or create_engine(url)
        metadata.configure(schema=schema)
        metadata().bind = self._engine


class Metadata:
    _metadata = None

    def __call__(self):
        return self._metadata

    def configure(self, **kwargs):
        self._metadata = self._metadata or MetaData(**kwargs)


engine = Engine()
metadata = Metadata()


def table(name, gtype, srid, fields):
    """Create an ``sqlalchemy.Table`` with a geometry column."""
    cols = [_make_column(f) for f in fields]
    if gtype == 'POLYGON':
        gtype = 'MULTIPOLYGON'
    elif gtype == 'LINESTRING':
        gtype = 'MULTILINESTRING'
    cols.append(Column('geom', Geometry(gtype, srid, spatial_index=False)))
    return Table(name, metadata(), *cols)


def table_name(table):
    schema = table.schema or 'public'
    name = table.name
    return '"{}"."{}"'.format(schema, name)


def _make_column(field):
    f_name, f_type, f_length, f_prec = field
    if f_type == 'C':
        return Column(f_name, Text)
    elif f_type == 'N':
        if f_prec == 0:
            return Column(f_name, Integer)
        else:
            return Column(f_name, Float)
    elif f_type == 'D':
        return Column(f_name, Date)
    elif f_type == 'L':
        return Column(f_name, Boolean)


def prep_field(field, _type, encoding):
    """Prepare a field to be written out for PostGres COPY.

    This uses the TEXT format with the default ``\\N`` marker for NULL
    values.
    """
    if field is None:
        return r'\N'
    if _type == 'C':
        if type(field) is bytes:
            field = field.decode(encoding)
        return quote.sub(r'\\\1', field)
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


class Wrapped(io.BufferedIOBase):
    """Buffered sequential reader.

    This is a pretty dumb shim to deal with the inefficiencies of treating
    an S3 object like a file. It's intended to only be used for wrapping
    a shapefile's files when being fed to the psycopg2 cursor's
    ``copy_from`` method. Don't use this when reading a zipfile. It will
    break.
    """
    def __init__(self, raw):
        self.raw = raw
        self.buffer = b''

    def seekable(self):
        return False

    def writable(self):
        return False

    def peek(self, size=-1):
        raise NotImplementedError

    def read1(self, size=-1):
        return self.read(size)

    def read(self, size=-1):
        if size is None or size < 0:
            return self.raw.read()
        else:
            while size > len(self.buffer):
                chunk = self.raw.read(S3_BUFFER_SIZE)
                if not chunk:
                    break
                self.buffer += chunk
            buf = self.buffer[:size]
            self.buffer = self.buffer[size:]
            return buf


class PGShapeReader:
    """Implements file-like interface to shapefile for PG COPY command.

    A ``PGShapeReader`` provides a streaming interface to a Shapefile for
    passing to a ``psycopg2`` cursor's ``copy_from`` method. The class
    requires a ``shapefile.Reader`` object from
    `pyshp <https://github.com/GeospatialPython/pyshp>`_.
    """
    def __init__(self, shapefile, srid, encoding='utf-8'):
        self.shapefile = shapefile
        self.srid = srid
        self.encoding = encoding
        self._f_types = [f[1] for f in self.shapefile.fields[1:]]
        self._g = self.shapefile.iterShapeRecords()
        self._buffer = u''

    def read(self, size=-1):
        if size <= 0:
            while True:
                try:
                    self._read_into_buffer()
                except StopIteration:
                    return self._buffer
        while len(self._buffer) < size:
            try:
                self._read_into_buffer()
            except StopIteration:
                break
        buf = self._buffer[:size]
        self._buffer = self._buffer[size:]
        return buf

    def readline(self):
        try:
            record = next(self._g)
        except StopIteration:
            return u''
        return self._record_to_str(record)

    def _read_into_buffer(self):
        record = next(self._g)
        self._buffer += self._record_to_str(record)

    def _record_to_str(self, record):
        geom = u'SRID={};{}'.format(
            self.srid, wkt.dumps(multiply(record.shape.__geo_interface__)))
        fields = [prep_field(f, f_type, self.encoding) for f, f_type in
                  zip(record.record, self._f_types)] + [geom]
        return u'\t'.join(fields) + u'\n'


def load_layer(layer):
    """Load the layer into PostGIS."""
    srid = layer.srid
    with Reader(shp=Wrapped(layer.shp), dbf=Wrapped(layer.dbf)) as sf:
        geom_type = GEOM_TYPES[sf.shapeType]
        fields = sf.fields[1:]
        t = table(layer.name, geom_type, srid, fields)
        if t.exists():
            raise Exception('Table {} already exists'.format(layer.name))
        t.create()
        try:
            with engine().begin() as conn:
                reader = PGShapeReader(sf, srid, layer.encoding)
                cursor = conn.connection.cursor()
                cursor.copy_from(reader, table_name(t))
            with engine().connect() as conn:
                conn.execute('CREATE INDEX "idx_{}_geom" ON {} USING GIST '
                             '(geom)'.format(layer.name, table_name(t)))
        except Exception:
            t.drop()
            raise
