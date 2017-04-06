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


def table(name, gtype, srid, fields, encoding):
    """Create an ``sqlalchemy.Table`` with a geometry column."""
    cols = [_make_column(f, encoding) for f in fields]
    if gtype == 'POLYGON':
        gtype = 'MULTIPOLYGON'
    elif gtype == 'LINESTRING':
        gtype = 'MULTILINESTRING'
    cols.append(Column('geom', Geometry(gtype, srid, spatial_index=False)))
    return Table(name, metadata, *cols)


def _make_column(field, encoding):
    f_name, f_type, f_length, f_prec = field
    if f_type == 'C':
        return Column(f_name, Text)
    elif f_type == 'N':
        if f_prec == 0:
            return Column(f_name, Integer)
        else:
            # TODO: Double?
            return Column(f_name, Float(precision=15))
    elif f_type == 'D':
        return Column(f_name, Date)
    elif f_type == 'L':
        return Column(f_name, Boolean)
