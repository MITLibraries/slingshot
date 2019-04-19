import os

from click.testing import CliRunner
import pytest
import requests_mock

from slingshot.cli import main
from slingshot.db import engine, metadata


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def db():
    uri = os.environ['PG_DATABASE']
    engine.configure(uri)
    if engine().has_table('bermuda', schema='geodata'):
        with engine().connect() as conn:
            conn.execute("DROP TABLE geodata.bermuda")
    metadata.clear()
    return engine


@pytest.mark.integration
def test_publishes_shapefile(db, runner, shapefile, s3):
    bucket = s3.Bucket("upload")
    bucket.upload_file(shapefile, "bermuda.zip")
    uri = os.environ['PG_DATABASE']
    with requests_mock.Mocker() as m:
        m.post("mock://example.com/geoserver/rest/workspaces/public/"
               "datastores/pg/featuretypes")
        m.post("mock://example.com/solr/update/json/docs")
        res = runner.invoke(main, ['publish', 'upload', 'bermuda.zip',
                                   'store', '--db-uri', uri, '--geoserver',
                                   'mock://example.com/geoserver/',
                                   '--solr', 'mock://example.com/solr'])
    assert res.exit_code == 0
    assert "Published bermuda" in res.output
    with db().connect() as conn:
        r = conn.execute('SELECT COUNT(*) FROM geodata.bermuda').scalar()
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
