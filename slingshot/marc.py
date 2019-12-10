from collections.abc import Iterator
from decimal import Decimal, getcontext
import re

from pymarc import MARCReader

from slingshot.app import make_slug
from slingshot.record import Record


COORD_REGEX = re.compile(
    r"""^(?P<hemisphere>[NSEW+-])?
         (?P<degrees>\d{3}(\.\d*)?)
         (?P<minutes>\d{2}(\.\d*)?)?
         (?P<seconds>\d{2}(\.\d*)?)?""", re.IGNORECASE | re.VERBOSE)


DC_FORMAT_S = {
    'MAP': 'Paper Map',
    'CDROM': 'Cartographic Material',
    'DVDROM': 'Cartographic Material',
}


def filter_record(record):
    return record.leader[5] in ('a', 'c', 'n', 'p') and \
           ('655' in record) and (record['655']['a'] == 'Maps.') and \
           ('852' in record) and \
           (formats(record).intersection(DC_FORMAT_S.keys())) and \
           (record['852']['c'] in ('MAPRM', 'GIS'))


def formats(record):
    return {sf for f in record.get_fields('852')
            for sf in f.get_subfields('k')}


class MarcParser(Iterator):
    def __init__(self, stream, f=None):
        self.reader = MARCReader(stream)
        if f:
            self.reader = filter(f, self.reader)

    def __next__(self):
        while True:
            try:
                record = next(self.reader)
            except StopIteration:
                raise
            except Exception:
                # pymarc doesn't handle broken MARC very well. A single bad
                # record will stop the whole train.
                continue
            if not record:
                continue
            ident = f'http://library.mit.edu/item/{record["001"].value()}'
            subjects = {sf for f in record.get_fields('650')
                        for sf in f.get_subfields('a')}
            spatial_subjects = {sf for f in record.get_fields('650')
                                for sf in f.get_subfields('z')}
            fmts = [DC_FORMAT_S[f] for f in formats(record)
                    if f in DC_FORMAT_S]
            if fmts:
                fmt = fmts[0]
            else:
                fmt = None
            if '034' in record and all([record['034'][s] for s in 'defg']):
                w = convert_coord(pad_034(record['034']['d']))
                e = convert_coord(pad_034(record['034']['e']))
                n = convert_coord(pad_034(record['034']['f']))
                s = convert_coord(pad_034(record['034']['g']))
                geom = f'ENVELOPE({w}, {e}, {n}, {s})'
            else:
                geom = None
            r = Record(
                dc_identifier_s=ident,
                dc_rights_s='Public',
                dc_title_s=record.title(),
                dc_publisher_s=record.publisher(),
                dc_creator_sm=[record.author()],
                dc_type_s='Physical Object',
                dct_references_s={'http://schema.org/url': ident},
                layer_geom_type_s='Mixed',
                dc_subject_sm=subjects,
                dct_spatial_sm=spatial_subjects,
                dct_temporal_sm=record.pubyear(),
                solr_geom=geom,
                dc_format_s=fmt,
                layer_slug_s=make_slug(ident),
            )
            return r


def convert_coord(coordinate, precision=10):
    o_precision = getcontext().prec
    getcontext().prec = precision
    matches = COORD_REGEX.search(coordinate)
    if not matches:
        return None
    parts = matches.groupdict()
    dec = Decimal(parts.get('degrees')) + \
        Decimal(parts.get('minutes') or 0) / 60 + \
        Decimal(parts.get('seconds') or 0) / 3600
    if parts.get('hemisphere') and \
       parts.get('hemisphere').lower() in 'ws-':
        dec = dec * -1
    getcontext().prec = o_precision
    return dec


def pad_034(coordinate):
    h, c = coordinate[0], coordinate[1:]
    if h in 'NSEW':
        c = "{:>07}".format(c)
    return h + c
