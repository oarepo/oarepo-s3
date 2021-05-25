# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 CESNET
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""S3 file storage support for Invenio. """

import os

from setuptools import find_packages, setup

readme = open('README.md').read()
history = open('CHANGES.rst').read()
OAREPO_VERSION = os.environ.get('OAREPO_VERSION', '3.3.0')

tests_require = [
    'moto[s3]>=1.3.16',
    'oarepo-records-draft>=5.5.2',
    'mock>=4.0.3'
]

extras_require = {
    'tests': [
        'oarepo[tests]~={version}'.format(version=OAREPO_VERSION),
        *tests_require
    ]
}

extras_require['all'] = []
for reqs in extras_require.values():
    extras_require['all'].extend(reqs)

setup_requires = [
    'pytest-runner>=3.0.0',
]

install_requires = [
    'invenio-s3==1.0.3',
]

packages = find_packages(exclude=['tests'])

# Get the version string. Cannot be done with import!
g = {}
with open(os.path.join('oarepo_s3', 'version.py'), 'rt') as fp:
    exec(fp.read(), g)
    version = g['__version__']

setup(
    name='oarepo-s3',
    version=version,
    description=__doc__,
    long_description=readme + '\n\n' + history,
    long_description_content_type='text/markdown',
    keywords='oarepo s3',
    license='MIT',
    author='Miroslav Bauer @ CESNET',
    author_email='bauer@cesnet.cz',
    url='https://github.com/oarepo/oarepo-s3',
    packages=packages,
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    entry_points={
        'invenio_base.api_apps': [
            'oarepo_s3 = oarepo_s3:OARepoS3',
        ],
        'invenio_base.apps': [
            'oarepo_s3 = oarepo_s3:OARepoS3',
        ],
        'oarepo_records_draft.uploaders': [
            'oarepo_s3 = oarepo_s3.api:multipart_uploader'
        ],
        'oarepo_records_draft.extra_actions': [
            'oarepo_s3 = oarepo_s3.views:multipart_actions'
        ],
        'invenio_celery.tasks': [
            'oarepo_s3 = oarepo_s3.tasks',
        ],
    },
    extras_require=extras_require,
    install_requires=install_requires,
    setup_requires=setup_requires,
    tests_require=tests_require,
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Development Status :: 4 - Beta',
    ],
)
