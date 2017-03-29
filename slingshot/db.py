from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Column,
    create_engine,
    Date,
    Float,
    func,
    Integer,
    MetaData,
    Table,
    Text,
    types,
)


class Engine(object):
    _engine = None

    def __call__(self):
        return self._engine

    def configure(self, url):
        self._engine = self._engine or create_engine(url)


engine = Engine()
metadata = MetaData()


class MultiGeom(Geometry):
    """Forces a geometry to its Multi* counterpart.

    This allows a table to load, for example, both polygons and
    multipolygons.
    """
    def bind_expression(self, bindvalue):
        return func.ST_Multi(func.ST_GeomFromEWKT(bindvalue, type_=self))


class Utf8Text(types.TypeDecorator):
    """SQLAlchemy type that forces the value to UTF-8.

    The third party ``pyshp`` module that we're using to read the shapefiles
    can return either bytes or unicode for character data. Unfortunately,
    a lot of the shapefile character data is mangled. In many cases, there's
    nothing we can do about this. This type will try its best to get usable
    character data. If it can successfully encode to UTF-8 the value will
    be added although, these may be hopelessly useless bytes.

    It will accept a ``provisional_encoding`` keyword argument (which can
    be pulled from the shapefile's .cst file, for example). If the field's
    value is a unicode object it will be encoded to UTF-8. If it is a
    ``bytes`` object it will try to decode using the ``provisional_encoding``
    and fall back to ISO-8859-1, before re-encoding to UTF-8. This is
    essentially the same behavior as OGR.
    """

    impl = Text

    def __init__(self, *args, **kwargs):
        self.encoding = kwargs.pop('provisional_encoding', 'ISO-8859-1')
        types.TypeDecorator.__init__(self, *args, **kwargs)

    def process_bind_param(self, value, dialect):
        if isinstance(value, bytes):
            value = value.decode(self.encoding)
            return value.encode('utf-8')
        try:
            return value.encode('utf-8')
        except:
            return value


def table(name, gtype, srid, fields, encoding):
    """Create an ``sqlalchemy.Table`` with a geometry column."""
    cols = [_make_column(f, encoding) for f in fields]
    if gtype == 'POLYGON':
        Geom = MultiGeom
        _gtype = 'MULTIPOLYGON'
    elif gtype == 'LINESTRING':
        Geom = MultiGeom
        _gtype = 'MULTILINESTRING'
    else:
        Geom = Geometry
        _gtype = gtype
    geom_c = Column('geom', Geom(_gtype, srid))
    return Table(name, metadata, geom_c, *cols)


def _make_column(field, encoding):
    f_name, f_type, f_length, f_prec = field
    if f_type == 'C':
        return Column(f_name, Utf8Text(provisional_encoding=encoding))
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
