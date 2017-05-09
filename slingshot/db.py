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


def prep_field(field, _type, encoding):
    """Prepare a field to be written out for PostGres COPY.

    This uses the TEXT format with the default ``\\N`` marker for NULL
    values.
    """
    if field is None:
        return r'\N'
    if _type == 'C':
        try:
            # This could be either bytes or unicode
            field = field.decode(encoding)
        except:
            pass
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
