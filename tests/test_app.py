# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import tempfile
import uuid

import pytest
import requests_mock

from slingshot.app import (
    create_record,
    GeoBag,
    get_srid,
    index_layer,
    make_bag_dir,
    make_slug,
    make_uuid,
    register_layer,
    unpack_zip,
)


@pytest.fixture
def temp_dir():
    return tempfile.mkdtemp()


def test_unpack_zip_extracts_to_top_of_dir(shapefile, temp_dir):
    unpack_zip(shapefile, temp_dir)
    assert os.path.isfile(os.path.join(temp_dir, 'bermuda.shp'))


def test_make_bag_dir_creates_directory(temp_dir):
    make_bag_dir('TEST_BAG', temp_dir)
    assert os.path.isdir(os.path.join(temp_dir, 'TEST_BAG'))


def test_make_bag_dir_returns_dir_name(temp_dir):
    assert make_bag_dir('TEST_BAG', temp_dir) == \
        os.path.join(temp_dir, 'TEST_BAG')


def test_make_bag_dir_raises_error_when_dir_exists(temp_dir):
    bag = os.path.join(temp_dir, 'TEST_BAG')
    os.mkdir(bag)
    with open(os.path.join(bag, 'foobar'), 'w') as fp:
        fp.write("I shouldn't be here.")
    with pytest.raises(OSError):
        make_bag_dir('TEST_BAG', temp_dir)


def test_make_bag_dir_overwrites_existing_dir(temp_dir):
    bag = os.path.join(temp_dir, 'TEST_BAG')
    os.mkdir(bag)
    with open(os.path.join(bag, 'foobar'), 'w') as fp:
        fp.write("I shouldn't be here.")
    make_bag_dir('TEST_BAG', temp_dir, overwrite=True)
    assert not os.path.isfile(os.path.join(bag, 'foobar'))


def test_create_record_creates_mit_record(bag):
    record = create_record(GeoBag(bag), public='mock://example.com',
                           secure='mock://example.com')
    assert record.dct_provenance_s == 'MIT'


def test_create_record_uses_correct_geoserver(bag):
    record = create_record(GeoBag(bag), public='mock://example.com/1',
                           secure='mock://example.com/2')
    assert record.dct_references_s.get(
        'http://www.opengis.net/def/serviceType/ogc/wms') == \
        'mock://example.com/1/wms'


def test_register_layer_adds_layer_to_geoserver():
    with requests_mock.Mocker() as m:
        m.post('mock://example.com/rest/workspaces/mit/datastores/'
               'data/featuretypes')
        register_layer('bermuda', 'mock://example.com/', 'mit', 'data')
        assert m.request_history[0].text == \
            '<featureType><name>bermuda</name></featureType>'


def test_index_layer_adds_layer_to_solr():
    with requests_mock.Mocker() as m:
        m.post('mock://example.com/update/json/docs')
        index_layer({'foo': 'bar'}, 'mock://example.com/')
        assert m.request_history[0].json() == {'foo': 'bar'}


def test_make_uuid_creates_uuid_string():
    assert make_uuid('bermuda', 'mit.edu') == \
        uuid.UUID('df04b29c-0e51-58a8-8a37-557e4f4917df')


def test_make_uuid_works_with_unicode_values():
    assert make_uuid(u'bermuda', u'mit.edu') == \
        uuid.UUID('df04b29c-0e51-58a8-8a37-557e4f4917df')


def test_make_slug_creates_slug():
    assert make_slug('bermuda') == 'mit-34clfhaokfmkq'


def test_geobag_create_creates_new_bag(shapefile_unpacked):
    b = GeoBag.create(shapefile_unpacked)
    assert b.is_valid()


def test_geobag_returns_access(bag):
    assert GeoBag(bag).is_public() == True


def test_geobag_returns_payload_dir(bag):
    assert GeoBag(bag).payload_dir == os.path.join(bag, 'data')


def test_geobag_returns_layer_name(bag):
    assert GeoBag(bag).name == 'bermuda'


def test_geobag_returns_record(bag):
    assert GeoBag(bag).record == \
        {u'dc_rights_s': u'Public', u'layer_slug_s': u'mit-34clfhaokfmkq'}


def test_geobag_writes_record(bag):
    b = GeoBag(bag)
    b.record = {'foo': 'bar'}
    with open(os.path.join(b.payload_dir, 'gbl_record.json')) as fp:
        rec = fp.read()
    assert rec == '{\"foo\": \"bar\"}'


def test_geobag_returns_path_to_fgdc(bag):
    assert GeoBag(bag).fgdc == os.path.join(bag, 'data/bermuda.xml')


def test_geobag_returns_path_to_shp_file(bag):
    assert GeoBag(bag).shp == os.path.join(bag, 'data/bermuda.shp')


def test_geobag_returns_path_to_prj_file(bag):
    assert GeoBag(bag).prj == os.path.join(bag, 'data/bermuda.prj')


def test_geobag_returns_path_to_cst_file(bag):
    assert GeoBag(bag).cst == os.path.join(bag, 'data/bermuda.cst')


def test_geobag_updates_bag_on_save(bag):
    b = GeoBag(bag)
    b.record = 'foobar'
    b.save()
    assert b.is_valid()


def test_get_srid_returns_as_int(prj_4326):
    assert get_srid(prj_4326) == 4326
