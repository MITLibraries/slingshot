import os

from click.testing import CliRunner
import pytest
import requests_mock

from slingshot.cli import main
from slingshot.db import engine, metadata


@pytest.fixture
def runner():
    if 'S3_ENDPOINT' in os.environ:
        del os.environ['S3_ENDPOINT']
    return CliRunner()


@pytest.fixture
def db():
    uri = os.environ['PG_DATABASE']
    schema = os.environ.get('PG_SCHEMA', 'public')
    engine.configure(uri, schema)
    if engine().has_table('bermuda', schema=schema):
        with engine().connect() as conn:
            conn.execute("DROP TABLE {}.bermuda".format(schema))
    metadata().clear()
    yield engine
    if engine().has_table('bermuda', schema=schema):
        with engine().connect() as conn:
            conn.execute("DROP TABLE {}.bermuda".format(schema))


@pytest.mark.integration
def test_publishes_shapefile(db, runner, shapefile, s3):
    bucket = s3.Bucket("upload")
    bucket.upload_file(shapefile, "bermuda.zip")
    uri = db().url
    schema = metadata().schema
    with requests_mock.Mocker() as m:
        m.post("mock://example.com/geoserver/rest/workspaces/public/"
               "datastores/pg/featuretypes")
        m.post("mock://example.com/solr/update/json/docs")
        res = runner.invoke(main, ['publish', 'upload', 'bermuda.zip',
                                   'store', '--db-uri', uri, '--db-schema',
                                   schema, '--geoserver',
                                   'mock://example.com/geoserver/',
                                   '--solr', 'mock://example.com/solr'])
    assert res.exit_code == 0
    assert "Published bermuda" in res.output
    with db().connect() as conn:
        r = conn.execute('SELECT COUNT(*) FROM {}.bermuda'.format(schema)) \
            .scalar()
        assert r == 713


@pytest.mark.integration
def test_publishes_geotiff(runner, geotiff, s3):
    bucket = s3.Bucket("upload")
    bucket.upload_file(geotiff, "france.zip")
    with requests_mock.Mocker() as m:
        m.post('mock://example.com/geoserver/rest/workspaces/secure'
               '/coveragestores')
        m.post('mock://example.com/geoserver/rest/workspaces/secure'
               '/coveragestores/france/coverages')
        m.post('mock://example.com/solr/update/json/docs')
        res = runner.invoke(main, ['publish', 'upload', 'france.zip',
                                   'store', '--geoserver',
                                   'mock://example.com/geoserver/',
                                   '--solr', 'mock://example.com/solr'])
        assert res.exit_code == 0
        assert 'Published france' in res.output


@pytest.mark.integration
def test_initializes_geoserver(runner):
    with requests_mock.Mocker() as m:
        m.post('mock://example.com/geoserver/rest/workspaces')
        m.post('mock://example.com/geoserver/rest/workspaces/public'
               '/datastores')
        m.post('mock://example.com/geoserver/rest/workspaces/secure'
               '/datastores')
        m.post('mock://example.com/geoserver/rest/security/acl/layers')
        m.put('mock://example.com/geoserver/rest/security/acl/layers')
        res = runner.invoke(main, ['initialize', '--geoserver',
                                   'mock://example.com/geoserver'])
        assert res.exit_code == 0
        assert m.call_count == 6
