import pytest

from slingshot.marc import MarcParser
from slingshot.record import Record


@pytest.fixture
def single_record():
    with open('tests/fixtures/map_01.mrc', 'rb') as fp:
        yield fp


def test_parser_returns_record(single_record):
    parser = MarcParser(single_record)
    record = Record(
        dc_identifier_s='http://library.mit.edu/item/002107286',
        dc_rights_s='Public',
        dc_title_s='Afghanistan country profile : '
                   'Afghanistan provinces and districts.',
        dc_publisher_s='[Central Intelligence Agency],',
        dc_creator_sm=['United States. Central Intelligence Agency.'],
        dc_type_s='Physical Object',
        dct_references_s={'http://schema.org/url':
                          'http://library.mit.edu/item/002107286'},
        layer_geom_type_s='Mixed',
        dc_subject_sm=['Geography', 'Area studies', 'Demography'],
        dct_spatial_sm=['Afghanistan'],
        dct_temporal_sm='[2012]',
        solr_geom='ENVELOPE(60, 74.5, 38.5, 29)',
        dc_format_s='Paper Map',
        layer_slug_s='mit-epowtnzw5fkdo',
    )
    assert next(parser) == record
