# -*- coding: utf-8 -*-
#
# Copyright (C) 2018, 2019 Esteban J. G. Gabancho.
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""Pytest configuration."""
from __future__ import absolute_import, print_function

import hashlib
import os
from io import BytesIO

import boto3
import pytest
from flask import current_app
from invenio_app.factory import create_api
from invenio_files_rest.models import Bucket, Location
from invenio_records_files.api import Record
from moto import mock_s3

from oarepo_s3 import S3FileStorage


@pytest.fixture(scope='module')
def app_config(app_config):
    """Customize application configuration."""
    from invenio_records_files.api import Record as RecordFiles

    app_config[
        'FILES_REST_STORAGE_FACTORY'] = 'oarepo_s3.storage.s3_storage_factory'
    app_config['S3_ENDPOINT_URL'] = None
    app_config['S3_ACCESS_KEY_ID'] = 'test'
    app_config['S3_SECRECT_ACCESS_KEY'] = 'test'
    app_config['FILES_REST_MULTIPART_CHUNKSIZE_MIN'] = 1024 * 1024 * 6
    # Endpoint with files support
    app_config['RECORDS_REST_ENDPOINTS'] = {
        'recid': {
            'pid_type': 'recid',
            'record_class': RecordFiles,
            'record_serializers': {
                'application/json': (),
            },
            'search_serializers': {
                'application/json': (),
            },
            'search_type': None,
            'search_index': None,
            'list_route': '/records/',
            'item_route': '/records/<pid(recid, '
                          'record_class="invenio_records_files.api.Record"):pid_value>',
            'indexer_class': None
        }
    }

    app_config.update(dict(
        S3_MULTIPART_UPLOAD_EXPIRATION=3600,
        SECRET_KEY='CHANGE_ME',
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            'SQLALCHEMY_DATABASE_URI', 'sqlite://'),
        SQLALCHEMY_TRACK_MODIFICATIONS=True,
        TESTING=True,
    ))

    return app_config


@pytest.fixture(scope='module')
def create_app():
    """Application factory fixture."""
    return create_api


@pytest.fixture(scope='function')
def s3_bucket(appctx):
    """S3 bucket fixture."""
    with mock_s3():
        session = boto3.Session(
            aws_access_key_id=current_app.config.get('S3_ACCESS_KEY_ID'),
            aws_secret_access_key=current_app.config.get(
                'S3_SECRECT_ACCESS_KEY'),
        )
        s3 = session.resource('s3')
        bucket = s3.create_bucket(Bucket='test_invenio_s3')

        yield bucket

        for obj in bucket.objects.all():
            obj.delete()
        bucket.delete()


@pytest.fixture(scope='function')
def s3storage(s3_bucket, s3_testpath):
    """Instance of S3FileStorage."""
    s3_storage = S3FileStorage(s3_testpath)
    return s3_storage


@pytest.fixture
def file_instance_mock(s3_testpath):
    """Mock of a file instance."""

    class FileInstance(object):
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    return FileInstance(
        id='deadbeef-65bd-4d9b-93e2-ec88cc59aec5',
        uri=s3_testpath,
        size=4,
        updated=None)


@pytest.fixture()
def get_md5():
    """Get MD5 of data."""

    def inner(data, prefix=True):
        m = hashlib.md5()
        m.update(data)
        return "md5:{0}".format(m.hexdigest()) if prefix else m.hexdigest()

    return inner


@pytest.fixture(scope='function')
def s3_testpath(s3_bucket):
    """S3 test path."""
    return 's3://{}/path/to/data'.format(s3_bucket.name)


@pytest.yield_fixture()
def s3_location(db, s3_testpath):
    """File system location."""
    loc = Location(
        name='testloc',
        uri=s3_testpath,
        default=True
    )
    db.session.add(loc)
    db.session.commit()

    yield loc


@pytest.yield_fixture()
def objects():
    """Test file contents."""
    objs = []
    for key, content in [
        ('LICENSE', b'license file'),
        ('README.rst', b'readme file')]:
        objs.append(
            (key, BytesIO(content), len(content))
        )
    yield objs


@pytest.fixture()
def bucket(db, s3_location):
    """File system location."""
    b1 = Bucket.create()
    db.session.commit()
    return b1


@pytest.fixture()
def generic_file(db, app, record):
    """Add a generic file to the record."""
    stream = BytesIO(b'test example')
    filename = 'generic_file.txt'
    record.files[filename] = stream
    record.files.dumps()
    record.commit()
    db.session.commit()
    return filename


@pytest.fixture()
def record(app, db, s3_location):
    """Create a record."""
    record = {
        'title': 'fuu'
    }
    record = Record.create(record)
    record.commit()
    db.session.commit()
    return record
