from plyplus import Grammar


parser = Grammar(r"""
    start: horiz_cs ;

    horiz_cs: geogcs | projcs ;
    geogcs: 'GEOGCS\[' name ',' datum ',' prime_meridian (',' angular_unit)?
           (',' twin_axes)? (',' authority)? '\]' ;
    projcs: 'PROJCS\[' name ',' geogcs ',' projection (',' parameter)* (','
            linear_unit)? (',' twin_axes)? (',' authority)? '\]' ;
    projection: 'PROJECTION\[' name (',' authority)? '\]' ;
    datum: 'DATUM\[' name ',' spheroid (',' to_wgs84)? (',' authority)? '\]' ;
    authority: 'AUTHORITY\[' name ',' code '\]' ;
    parameter : 'PARAMETER\[' name ',' number '\]' ;
    spheroid : 'SPHEROID\[' name ',' semi_major_axis ',' inverse_flattening
               (',' authority)? '\]' ;
    semi_major_axis : number ;
    inverse_flattening : number ;
    to_wgs84 : 'TOWGS84\[' dx ',' dy ',' dz ',' ex ',' ey ',' ez ',' ppm '\]' ;
    prime_meridian : 'PRIMEM\[' name ',' longitude (',' authority)? '\]' ;
    longitude : number ;
    linear_unit: unit ;
    angular_unit: unit ;
    unit : 'UNIT\[' name ',' conversion_factor (',' authority)? '\]' ;
    conversion_factor : number ;
    twin_axes : axis ',' axis ;
    axis : 'AXIS\[' name ',' ('NORTH' | 'SOUTH' | 'EAST' | 'WEST' | 'UP' |
           'DOWN' | 'OTHER') '\]' ;
    number : '[+-]?([0-9]*[.])?[0-9]+' ;
    name : '"([^"])+"' ;
    code: '"([0-9])+"' ;
    dx : number ;
    dy : number ;
    dz : number ;
    ex : number ;
    ey : number ;
    ez : number ;
    ppm : number ;

    WS: '[\s\n]+' (%ignore) ;
""")
