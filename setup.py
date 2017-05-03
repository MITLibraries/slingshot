# -*- coding: utf-8 -*-
"""
Slingshot
=========

Create and submit bags to kepler.
"""

import io
import re
from setuptools import find_packages, setup


with io.open('LICENSE') as f:
    license = f.read()

with io.open('slingshot/__init__.py', 'r') as fp:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', fp.read(),
                        re.MULTILINE).group(1)

setup(
    name='slingshot',
    version=version,
    description='Create and submit bags',
    long_description=__doc__,
    url='https://github.com/MITLibraries/slingshot',
    license=license,
    author='Mike Graves',
    author_email='mgraves@mit.edu',
    packages=find_packages(exclude=['tests']),
    install_requires=[
        'arrow',
        'bagit',
        'click',
        'geoalchemy2',
        'geomet',
        'plyplus',
        'psycopg2',
        'pyshp',
        'requests',
    ],
    setup_requires=[
        'pytest-runner',
    ],
    tests_require=[
        'pytest',
        'requests-mock',
    ],
    entry_points={
        'console_scripts': [
            'slingshot = slingshot.cli:main',
        ]
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Environment :: Console',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ]
)
