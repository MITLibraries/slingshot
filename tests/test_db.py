import pytest
from sqlalchemy import Boolean, Date, Float, Integer, Text

from slingshot.db import (
    metadata,
    multiply,
    prep_field,
    table,
    _make_column,
)


@pytest.fixture(autouse=True)
def reset_metadata():
    metadata.clear()


def test_table_converts_to_multi_geom_type():
    t = table('FOOBAR', 'POLYGON', 4326, [('f_1', 'C', 254, 0)])
    assert t.c.geom.type.geometry_type == 'MULTIPOLYGON'
    t = table('FOOBAZ', 'LINESTRING', 4326, [('f_1', 'C', 254, 0)])
    assert t.c.geom.type.geometry_type == 'MULTILINESTRING'


def test_table_adds_all_fields():
    t = table('FOOBAR', 'POINT', 4326, [('f_1', 'C', 254, 0),
                                        ('f_2', 'C', 254, 0)])
    assert t.c.geom.name == 'geom'
    assert t.c.f_1.name == 'f_1'
    assert t.c.f_2.name == 'f_2'


def test_make_column_creates_text_field():
    c = _make_column(('f', 'C', 254, 0))
    assert isinstance(c.type, Text)


def test_make_column_creates_integer_field():
    c = _make_column(('f', 'N', 10, 0))
    assert isinstance(c.type, Integer)


def test_make_column_creates_float_field():
    c = _make_column(('f', 'N', 10, 15))
    assert isinstance(c.type, Float)


def test_make_column_creates_date_field():
    c = _make_column(('f', 'D', 10, 0))
    assert isinstance(c.type, Date)


def test_make_column_creates_boolean_field():
    c = _make_column(('f', 'L', 1, 0))
    assert isinstance(c.type, Boolean)


def test_prep_field_returns_null_character_for_none():
    assert prep_field(None, 'C', None) == u'\u005cN'


def test_prep_field_returns_unicode_for_character_data():
    assert prep_field(b'\x83', 'C', 'cp1252') == u'\u0192'
    assert prep_field(u'\u0192', 'C', 'iso-8859-1') == u'\u0192'


def test_prep_field_escapes_characters():
    assert prep_field(b'foo\x09bar', 'C', 'iso-8859-1') == \
        u'foo\u005c\u0009bar'


def test_prep_field_casts_numbers_to_strings():
    assert prep_field(23, 'N', None) == '23'
    assert prep_field(1.0, 'N', None) == '1.0'


def test_multiply_converts_geojson_to_multi():
    assert multiply({'type': 'Polygon',
                     'coordinates': [[[0, 0], [1, 0], [1, 1], [0, 0]]]}) == \
        {'type': 'MultiPolygon',
         'coordinates': [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]}
    assert multiply({'type': 'LineString',
                     'coordinates': [[0, 0], [1, 0]]}) == \
        {'type': 'MultiLineString', 'coordinates': [[[0, 0], [1, 0]]]}


def test_multiply_does_not_modify_points():
    p = {'type': 'Point', 'coordinates': [0, 0]}
    assert multiply(p) == p
