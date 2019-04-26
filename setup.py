"""
Slingshot
=========

GIS data workflow.
"""

from setuptools import find_packages, setup


with open('LICENSE') as f:
    license = f.read()


setup(
    name='slingshot',
    version='1.0.0',
    description='GIS data workflow',
    long_description=__doc__,
    url='https://github.com/MITLibraries/slingshot',
    license=license,
    author='Mike Graves',
    author_email='mgraves@mit.edu',
    packages=find_packages(exclude=['tests']),
    install_requires=[
        'attrs',
        'boto3',
        'click',
        'geoalchemy2',
        'geomet',
        'plyplus',
        'psycopg2-binary',
        'pymarc',
        'pyshp',
        'requests',
    ],
    python_requires='>=3.7.1',
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
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
    ]
)
