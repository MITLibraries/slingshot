from geoalchemy2 import Geometry
from geomet import wkt
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


class Engine(object):
    _engine = None

    def __call__(self):
        return self._engine

    def configure(self, url):
        self._engine = self._engine or create_engine(url)


engine = Engine()
metadata = MetaData()


def table(name, gtype, srid, fields):
    """Create an ``sqlalchemy.Table`` with a geometry column."""
    cols = [_make_column(f) for f in fields]
    if gtype == 'POLYGON':
        gtype = 'MULTIPOLYGON'
    elif gtype == 'LINESTRING':
        gtype = 'MULTILINESTRING'
    cols.append(Column('geom', Geometry(gtype, srid, spatial_index=False)))
    return Table(name, metadata, *cols)


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
        quotable = (u'\t', u'\n', u'\r', u'\.')
        for q in quotable:
            field = field.replace(q, u'\\' + q)
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


class PGShapeReader(object):
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
