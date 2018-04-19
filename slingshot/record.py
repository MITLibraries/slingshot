from datetime import datetime
from functools import partial
from itertools import repeat
import json
import re

import attr
from attr import converters, validators


RIGHTS = ('Public', 'Restricted')
TYPES = ('Dataset', 'Image', 'Physical Object')
GEOMS = ('Point', 'Line', 'Polygon', 'Raster', 'Scanned Map', 'Mixed')

env_regex = re.compile(
    "ENVELOPE\({}, {}, {}, {}\)".format(*repeat("[+-]?\d+(\.\d+)?", 4)))
Field = partial(attr.ib, default=None)
_set = converters.optional(set)


def one_of(items):
    """A validator for checking membership in ``items``."""
    return validators.optional(validators.in_(items))


def rights_converter(term):
    """A converter for normalizing the rights string.

    This is based on the assumption that the FGDC rights statement will
    contain the word ``unrestricted`` when a layer is public and
    ``restricted`` when it is not.
    """
    if term.lower().startswith('unrestricted'):
        return 'Public'
    elif term.lower().startswith('restricted'):
        return 'Restricted'
    return term


def geom_converter(term):
    """A converter for normalizing the geometry type."""
    if 'point' in term.lower():
        return 'Point'
    elif 'string' in term.lower():
        return 'Line'
    elif any(v_type in term.lower() for v_type in ['polygon', 'chain']):
        return 'Polygon'
    elif 'composite' in term.lower():
        return 'Mixed'
    elif 'raster' in term.lower():
        return 'Raster'
    return term


def envelope_validator(instance, attribute, value):
    """A validator for checking the format of the envelope string."""
    if not env_regex.fullmatch(value):
        raise ValueError('Invalid envelope string')


def now():
    """Current UTC datetime string suitable for use as a Solr dt field."""
    return datetime.utcnow().isoformat(timespec='seconds') + 'Z'


def solr_dt(instance, attribute, value):
    """A validator for ensuring a datetime string is Solr compatible."""
    datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')


def _filter(attribute, value):
    if value and not attribute.name.startswith('_'):
        return True


@attr.s(frozen=True)
class Record:
    """A GeoBlacklight record.

    This is an immutable GeoBlacklight record object. The only supported
    fields are the ones defined as properties in the class definition. A
    record can be created by passing fields as keyword arguments to the
    constructor::

        r = Record(dc_title_s='Bermuda')

    While you cannot modify an existing record, you can create a new one
    based off the old one by using the ``attr.evolve`` function::

        import attr

        r = Record(dc_title_s='Bermuda')
        r = attr.evolve(r, dc_title_s='Bahamas')

    """
    dc_creator_sm = Field(converter=_set)
    dc_description_s = Field()
    dc_format_s = Field()
    dc_identifier_s = Field()
    dc_language_s = Field()
    dc_publisher_s = Field()
    dc_rights_s = Field(validator=one_of(RIGHTS),
                        converter=converters.optional(rights_converter))
    dc_source_sm = Field(converter=_set)
    dc_subject_sm = Field(converter=_set)
    dc_title_s = Field()
    dc_type_s = Field(validator=one_of(TYPES))
    dct_isPartOf_sm = Field(converter=_set)
    dct_issued_dt = Field()
    dct_provenance_s = Field(default='MIT')
    dct_spatial_sm = Field(converter=_set)
    dct_temporal_sm = Field(converter=_set)
    dct_references_s = Field(validator=validators.optional(
                                validators.instance_of(dict)))
    layer_geom_type_s = Field(validator=one_of(GEOMS),
                              converter=converters.optional(geom_converter))
    layer_id_s = Field()
    layer_modified_dt = Field(default=attr.Factory(now), validator=solr_dt)
    layer_slug_s = Field()
    solr_geom = Field(validator=validators.optional(envelope_validator))
    geoblacklight_version = Field(default='1.0')

    @classmethod
    def from_file(cls, path):
        """Create a record from the given JSON file."""
        with open(path, encoding='utf-8') as fp:
            record = json.load(fp)
        for k, v in record.items():
            if k == 'dct_references_s':
                record[k] = json.loads(v)
        return cls(**record)

    def to_file(self, path):
        """Save the record to the given file as JSON."""
        with open(path, 'w', encoding='utf-8') as fp:
            json.dump(self.as_dict(), fp, ensure_ascii=False)

    def as_dict(self):
        """Return record as dictionary.

        The returned dictionary will have all empty fields removed, as well
        as all fields beginning with an underscore. The ``dct_references_s``
        field will be serialzed to a JSON formatted string.

        This dictionary should be suitable for passing directly to
        ``json.dump`` or for loading directly into Solr, for example.
        """
        record = attr.asdict(self, filter=_filter)
        if 'dct_references_s' in record:
            record['dct_references_s'] = json.dumps(record['dct_references_s'])
        return record
