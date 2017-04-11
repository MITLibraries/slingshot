from slingshot.proj import parser


def test_parser_parses_projcs(prj_2249):
    with open(prj_2249) as fp:
        prj = fp.read()
    res = parser.parse(prj)
    assert res.select('projcs > authority > code *')[0] == '"2249"'


def test_parser_parses_geogcs(prj_4326):
    with open(prj_4326) as fp:
        prj = fp.read()
    res = parser.parse(prj)
    assert res.select('geogcs > authority > code *')[0] == '"4326"'
