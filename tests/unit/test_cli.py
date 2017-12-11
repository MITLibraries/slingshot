import os

from click.testing import CliRunner
import pytest
import requests_mock

from slingshot.cli import main


@pytest.fixture
def runner():
    return CliRunner()


def test_publish_publishes_layer(runner, bags_dir, meta_dir):
    with requests_mock.Mocker() as m:
        m.post('mock://example.com/public/rest/workspaces/mit/datastores'
               '/data/featuretypes')
        m.post('mock://example.com/solr/update')
        m.post('mock://example.com/solr/update/json/docs')
        res = runner.invoke(main, ['publish', '--public',
                                   'mock://example.com/public', '--secure',
                                   'mock://example.com/secure', '--solr',
                                   'mock://example.com/solr',
                                   '--metadata', meta_dir, bags_dir])
        assert res.exit_code == 0
        assert 'Loaded bermuda' in res.output
        assert 'bermuda.xml' in os.listdir(meta_dir)


def test_reindex_deletes_and_reloads(runner, bags_dir):
    with requests_mock.Mocker() as m:
        m.post('mock://example.com/solr/update')
        m.post('mock://example.com/solr/update/json/docs')
        res = runner.invoke(main, ['reindex', '--solr',
                                   'mock://example.com/solr', bags_dir])
        assert res.exit_code == 0
        assert m.request_history[0].json() == \
            {'delete': {'query':
                        'dct_provenance_s:MIT AND dc_format_s:Shapefile'}}
        assert 'Indexed bermuda' in res.output
        assert m.request_history[2].json() == {'commit': {}}
