import os
import shutil
import tempfile
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from click.testing import CliRunner
import pytest
import requests_mock

from slingshot.cli import main


@pytest.fixture
def runner():
    return CliRunner()


def test_bag_creates_bag(runner, shapefile):
    store = tempfile.mkdtemp()
    layers = tempfile.mkdtemp()
    shutil.copy2(shapefile, layers)
    with patch('slingshot.cli.load_layer'):
        res = runner.invoke(main, ['bag', '--db-uri', 'sqlite://', '--public',
                                   'mock://example.com', '--secure',
                                   'mock://example.com', layers, store])
    assert res.exit_code == 0
    assert 'Loaded layer bermuda' in res.output


def test_bag_skips_existing_layers(runner, shapefile, bags_dir):
    with patch('slingshot.cli.load_layer'):
        res = runner.invoke(main, ['bag', '--db-uri', 'sqlite://', '--public',
                                   'mock://example.com', '--secure',
                                   'mock://example.com', shapefile, bags_dir])
    assert res.exit_code == 0
    assert 'Skipping existing layer bermuda' in res.output


def test_bag_removes_failed_bag(runner, shapefile):
    store = tempfile.mkdtemp()
    with patch('slingshot.cli.load_layer') as m:
        m.side_effect = Exception
        res = runner.invoke(main, ['bag', '--db-uri', 'sqlite://', '--public',
                                   'mock://example.com', '--secure',
                                   'mock://example.com', shapefile, store])
        assert res.exit_code == 0
        assert 'Failed creating bag bermuda' in res.output
        assert not os.listdir(store)


def test_publish_publishes_layer(runner, bags_dir):
    with requests_mock.Mocker() as m:
        m.post('mock://example.com/public/rest/workspaces/mit/datastores'
               '/data/featuretypes')
        m.post('mock://example.com/solr/update/json/docs')
        res = runner.invoke(main, ['publish', '--public',
                                   'mock://example.com/public', '--secure',
                                   'mock://example.com/secure', '--solr',
                                   'mock://example.com/solr', bags_dir])
        assert res.exit_code == 0
        assert 'Loaded bermuda' in res.output


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
