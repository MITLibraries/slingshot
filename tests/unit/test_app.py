import json
import os
import tempfile
import uuid

import attr
import bagit
import pytest
import requests_mock

from slingshot.app import (
    add_layer,
    create_record,
    GeoBag,
    GeoServer,
    get_srid,
    load_bag,
    make_bag,
    make_slug,
    make_uuid,
    ShapeBag,
    Solr,
    unpack_zip,
)


@pytest.fixture
def temp_dir():
    return tempfile.mkdtemp()


def test_unpack_zip_extracts_to_top_of_dir(shapefile, temp_dir):
    unpack_zip(shapefile, temp_dir)
    assert os.path.isfile(os.path.join(temp_dir, 'bermuda.shp'))


def test_unpack_raises_error_for_unsupported_format(no_shp, temp_dir):
    with pytest.raises(Exception):
        unpack_zip(no_shp, temp_dir)


def test_create_record_creates_mit_record(bag):
    record = create_record(load_bag(bag), 'mock://example.com',
                           'mock://example.com', 'mit')
    assert record.dct_provenance_s == 'MIT'


def test_create_record_uses_correct_geoserver(bag):
    record = create_record(load_bag(bag), 'mock://example.com/1',
                           'mock://example.com/2', 'mit')
    assert record.dct_references_s.get(
        'http://www.opengis.net/def/serviceType/ogc/wms') == \
        'mock://example.com/1/wms'


def test_add_layer_adds_shapefile_to_geoserver(bag):
    b = load_bag(bag)
    with requests_mock.Mocker() as m:
        m.post('mock://example.com/rest/workspaces/mit/datastores/'
               'data/featuretypes')
        gs = GeoServer('mock://example.com')
        add_layer(b, gs, workspace='mit', datastore='data')
        assert m.request_history[0].text == \
            '<featureType><name>bermuda</name></featureType>'


def test_solr_adds_layer_to_solr():
    with requests_mock.Mocker() as m:
        m.post('mock://example.com/update/json/docs')
        s = Solr('mock://example.com/')
        s.add({'foo': 'bar'})
        assert m.request_history[0].json() == {'foo': 'bar'}


def test_solr_deletes_by_query():
    with requests_mock.Mocker() as m:
        m.post('mock://example.com/update')
        s = Solr('mock://example.com/')
        s.delete()
        assert m.request_history[0].json() == \
            {'delete': {'query': 'dct_provenance_s:MIT'}}


def test_solr_commits_changes():
    with requests_mock.Mocker() as m:
        m.post('mock://example.com/update')
        s = Solr('mock://example.com/')
        s.commit()
        assert m.request_history[0].json() == {'commit': {}}


def test_make_uuid_creates_uuid_string():
    assert make_uuid('bermuda', 'mit.edu') == \
        uuid.UUID('df04b29c-0e51-58a8-8a37-557e4f4917df')


def test_make_slug_creates_slug():
    assert make_slug('bermuda') == 'mit-34clfhaokfmkq'


def test_make_bag_creates_new_bag(shapefile_unpacked):
    b = make_bag(shapefile_unpacked)
    assert b.is_valid()


def test_geobag_returns_access(bag):
    assert GeoBag(bagit.Bag(bag)).is_public()


def test_geobag_returns_payload_dir(bag):
    assert GeoBag(bag).payload_dir == os.path.join(bag, 'data')


def test_shapebag_returns_layer_name(bag):
    b = ShapeBag(bagit.Bag(bag))
    assert b.name == 'bermuda'


def test_geobag_returns_record(bag):
    assert GeoBag(bagit.Bag(bag)).record.layer_slug_s == u'mit-34clfhaokfmkq'


def test_geobag_writes_record_on_save(bag):
    b = GeoBag(bagit.Bag(bag))
    b.record = attr.evolve(b.record, dc_title_s='Fooɓar')
    b.save()
    with open(os.path.join(b.payload_dir, 'gbl_record.json')) as fp:
        rec = json.load(fp)
    assert rec['dc_title_s'] == "Fooɓar"


def test_geobag_returns_path_to_fgdc(bag):
    assert GeoBag(bagit.Bag(bag)).fgdc == os.path.join(bag, 'data/bermuda.xml')


def test_shapebag_returns_path_to_shp_file(bag):
    assert ShapeBag(bagit.Bag(bag)).shp == os.path.join(bag,
                                                        'data/bermuda.shp')


def test_shapebag_returns_path_to_prj_file(bag):
    assert ShapeBag(bagit.Bag(bag)).prj == os.path.join(bag,
                                                        'data/bermuda.prj')


def test_shapebag_returns_path_to_cst_file(bag):
    assert ShapeBag(bagit.Bag(bag)).cst == os.path.join(bag,
                                                        'data/bermuda.cst')


def test_geobag_updates_bag_on_save(bag):
    b = GeoBag(bagit.Bag(bag))
    b.record = attr.evolve(b.record, dc_title_s='foobar')
    b.save()
    assert b.is_valid()


def test_get_srid_returns_as_int(prj_4326):
    assert get_srid(prj_4326) == 4326
