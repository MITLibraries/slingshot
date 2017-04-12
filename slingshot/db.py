from geoalchemy2 import Geometry
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
        quotable = (b'\t', b'\n', b'\r', b'\.')
        for q in quotable:
            field = field.replace(q, b'\\' + q)
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
