from collections.abc import Iterator
from decimal import Decimal, getcontext
import re

from pymarc import Record

from slingshot.app import make_slug


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


RECORD_TERMINATOR = b'\x1d'


def filter_record(record):
    if not record:
        return False
    return record.leader[5] in ('a', 'c', 'n', 'p') and \
        ('655' in record) and 'Maps.' in form(record) and \
        ('852' in record) and \
        (formats(record).intersection(DC_FORMAT_S.keys())) and \
        (record['852']['c'] in ('MAPRM', 'GIS'))


def form(record):
    return {sf for f in record.get_fields('655')
            for sf in f.get_subfields('a')}


def formats(record):
    return {sf for f in record.get_fields('852')
            for sf in f.get_subfields('k')}


class BadMARCReader(Iterator):
    """A liberal pymarc parser.

    The parser that comes with pymarc does a poor job of handling incorrect
    MARC data. Rather than using the reported record length to extract
    records this uses the record terminator. It's possible that some records
    may be missing the terminator but the parser should be able to recover
    at the expense of losing a few records. In this case, we know our data
    is bad and we'd rather take whatever we can get and drop the rest.
    """
    def __init__(self, stream):
        self.__buffer = b''
        self.stream = stream

    def __next__(self):
        chunk = b''
        while True:
            idx = self.__buffer.find(RECORD_TERMINATOR)
            if idx >= 0:
                chunk = self.__buffer[:idx]
                self.__buffer = self.__buffer[idx+1:]
                # In case the buffer starts with a record terminator, keep
                # trying until we have a record or reach the end.
                if not chunk:
                    continue
                break
            data = self.stream.read(8192)
            if not data:
                break
            self.__buffer += data
        if not chunk:
            raise StopIteration
        return Record(chunk, force_utf8=True)


class MarcParser(Iterator):
    def __init__(self, stream, f=None):
        self.reader = BadMARCReader(stream)
        if f:
            self.reader = filter(f, self.reader)

    def __next__(self):
        while True:
            try:
                record = next(self.reader)
            except UnicodeDecodeError:
                # skip records that can't be parsed
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
            r = dict(
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
