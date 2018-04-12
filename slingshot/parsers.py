try:
    from lxml.etree import iterparse
except ImportError:
    from xml.etree.ElementTree import iterparse


def parse(fp, parser):
    """
    Parse XML data using the specified parser.

    A parser class must implement at least two methods,
    ``start_handler`` and ``end_handler``, which accept an ``Element``.
    These methods must populate an instance property ``record`` which is
    returned when parsing is complete.

    :param source: file name or file pointer containing XML data
    :param parser: parser class to use for parsing
    """

    parser = parser()
    for event, elem in iterparse(fp, events=('start', 'end')):
        if event == 'start':
            parser.start_handler(elem)
        else:
            parser.end_handler(elem)
            elem.clear()
    return parser.record


class FGDCParser(object):
    """An FGDC XML parser."""

    def __init__(self):
        #: Parsed GeoBlacklight record
        self.record = {}
        self.stack = []

    def start_handler(self, elem):
        """
        Start handler called when encountering a new element.
        """
        self.stack.append(elem.tag)

    def end_handler(self, elem):
        """End handler called when encountering the end of an element."""

        if elem.tag == 'title' and self.stack[-3] == 'citation' and elem.text:
            self.record['dc_title_s'] = elem.text
        elif elem.tag == 'origin' and elem.text:
            self.record.setdefault('dc_creator_sm', set()).add(elem.text)
        elif elem.tag == 'abstract' and elem.text:
            self.record['dc_description_s'] = elem.text
        elif elem.tag == 'publish' and elem.text:
            self.record['dc_publisher_s'] = elem.text
        elif elem.tag == 'westbc' and elem.text:
            self.record['_bbox_w'] = elem.text
        elif elem.tag == 'eastbc' and elem.text:
            self.record['_bbox_e'] = elem.text
        elif elem.tag == 'northbc' and elem.text:
            self.record['_bbox_n'] = elem.text
        elif elem.tag == 'southbc' and elem.text:
            self.record['_bbox_s'] = elem.text
        elif elem.tag == 'accconst' and elem.text:
            self.record['dc_rights_s'] = elem.text
        elif elem.tag == 'themekey' and elem.text:
            if 'urn' in elem.attrib:
                self.record.setdefault('dc_subject_sm', set()).add(elem.text)
        elif elem.tag == 'placekey' and elem.text:
            if 'urn' in elem.attrib:
                self.record.setdefault('dct_spatial_sm', set()).add(elem.text)
        elif elem.tag == 'direct' and elem.text:
            if elem.text.lower() == 'raster':
                self.record['layer_geom_type_s'] = elem.text
        elif elem.tag == 'sdtstype' and elem.text:
            self.record['layer_geom_type_s'] = elem.text
        self.stack.pop()
