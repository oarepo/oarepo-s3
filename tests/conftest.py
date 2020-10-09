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
import shutil
import sys
import uuid
from io import BytesIO

import boto3
import pytest
from flask import Flask, current_app, url_for
from flask.testing import FlaskClient
from invenio_app.factory import create_api
from invenio_base.signals import app_loaded
from invenio_db import InvenioDB
from invenio_db import db as _db
from invenio_files_rest import InvenioFilesREST
from invenio_files_rest.models import Bucket, Location
from invenio_indexer import InvenioIndexer
from invenio_indexer.api import RecordIndexer
from invenio_jsonschemas import InvenioJSONSchemas
from invenio_pidstore import InvenioPIDStore
from invenio_pidstore.models import PersistentIdentifier, PIDStatus
from invenio_records import InvenioRecords
from invenio_records_files.api import Record
from invenio_records_rest import InvenioRecordsREST
from invenio_records_rest.utils import PIDConverter, allow_all
from invenio_records_rest.views import create_blueprint_from_app
from invenio_rest import InvenioREST
from invenio_search import InvenioSearch
from invenio_search.cli import destroy, init
from marshmallow import INCLUDE, Schema, fields
from mock import patch
from moto import mock_s3
from oarepo_records_draft.ext import RecordsDraft
from oarepo_validate import MarshmallowValidatedRecordMixin, \
    SchemaKeepingRecordMixin
from s3_client_lib.utils import get_file_chunk_size
from sqlalchemy_utils import create_database, database_exists

from invenio_s3 import InvenioS3
from oarepo_s3 import S3FileStorage
from oarepo_s3.ext import OARepoS3
from oarepo_s3.s3 import S3Client
from tests.utils import draft_entrypoints

SAMPLE_ALLOWED_SCHEMAS = [
    'http://localhost:5000/schemas/records/record-v1.0.0.json']
SAMPLE_PREFERRED_SCHEMA = \
    'http://localhost:5000/schemas/records/record-v1.0.0.json'


class TestSchemaV1(Schema):
    """Testing record schema."""

    title = fields.String()

    class Meta:
        """Test schema Meta class."""

        unknown = INCLUDE


class TestRecord(SchemaKeepingRecordMixin,
                 MarshmallowValidatedRecordMixin,
                 Record):
    """Fake test record."""

    ALLOWED_SCHEMAS = SAMPLE_ALLOWED_SCHEMAS
    PREFERRED_SCHEMA = SAMPLE_PREFERRED_SCHEMA
    MARSHMALLOW_SCHEMA = TestSchemaV1


class TestIndexer(RecordIndexer):
    """Fake record indexer."""

    def index(self, record, arguments=None, **kwargs):
        """Fake index implementation."""
        return {}


class MockedS3Client(S3Client):
    """Fake S3 client."""

    def init_multipart_upload(self, bucket, object_name, object_size):
        """Fake init multipart upload implementation."""
        max_parts, chunk_size = get_file_chunk_size(object_size)
        parts = [f'http://localhost/test/{i}' for i in range(1, max_parts + 1)]
        return {"parts_url": parts,
                "chunk_size": chunk_size,
                "checksum_update": "",
                "upload_id": str(uuid.uuid4()),
                "origin": "",
                "num_chunks": max_parts,
                "finish_url": ""
                }

    def complete_multipart_upload(self, bucket, object_name, parts, upload_id):
        """Faked complete of a multipart upload to AWS S3."""
        return {'status': 'completed'}

    def abort_multipart_upload(self, bucket, object_name, upload_id):
        """Faked cancel of an in-progress multipart upload to AWS S3."""
        return {'status': 'aborted'}


class JsonClient(FlaskClient):
    """Test REST JSON client."""

    def open(self, *args, **kwargs):
        """Opens a new connection."""
        kwargs.setdefault('content_type', 'application/json')
        kwargs.setdefault('Accept', 'application/json')
        return super().open(*args, **kwargs)


@pytest.fixture(scope='module')
def base_app(app_config):
    """Flask applicat-ion fixture."""
    instance_path = os.path.join(sys.prefix, 'var', 'test-instance')

    # empty the instance path
    if os.path.exists(instance_path):
        shutil.rmtree(instance_path)
    os.makedirs(instance_path)

    os.environ['INVENIO_INSTANCE_PATH'] = instance_path

    app_ = Flask('oarepo-s3-testapp', instance_path=instance_path)
    app_.config.update(
        TESTING=True,
        JSON_AS_ASCII=True,
        SQLALCHEMY_TRACK_MODIFICATIONS=True,
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            'SQLALCHEMY_DATABASE_URI',
            'sqlite:///:memory:'),
        SERVER_NAME='localhost:5000',
        SECURITY_PASSWORD_SALT='TEST_SECURITY_PASSWORD_SALT',
        SECRET_KEY='TEST_SECRET_KEY',
        INVENIO_INSTANCE_PATH=instance_path,
        # SEARCH_INDEX_PREFIX='records-',
        RECORDS_REST_ENDPOINTS={},
        SEARCH_INDEX_PREFIX='test-',
        FILES_REST_DEFAULT_STORAGE_CLASS='S',
        JSONSCHEMAS_HOST='localhost:5000',
        SEARCH_ELASTIC_HOSTS=os.environ.get('SEARCH_ELASTIC_HOSTS', None)
    )
    app_.config.update(**app_config)
    app.test_client_class = JsonClient

    from oarepo_s3 import config  # noqa

    InvenioDB(app_)
    InvenioFilesREST(app_)
    InvenioS3(app_)
    InvenioIndexer(app_)
    InvenioSearch(app_)
    RecordsDraft(app_)
    OARepoS3(app_)

    return app_


@pytest.yield_fixture(scope='module')
def app(base_app):
    """Flask application fixture."""
    base_app._internal_jsonschemas = InvenioJSONSchemas(base_app)
    InvenioREST(base_app)
    InvenioRecordsREST(base_app)
    InvenioRecords(base_app)
    InvenioPIDStore(base_app)
    base_app.url_map.converters['pid'] = PIDConverter
    base_app.register_blueprint(create_blueprint_from_app(base_app))

    app_loaded.send(None, app=base_app)

    with base_app.app_context():
        yield base_app


@pytest.fixture
def db(app):
    """Create database for the tests."""
    with app.app_context():
        if not database_exists(str(_db.engine.url)) and \
           app.config['SQLALCHEMY_DATABASE_URI'] != 'sqlite://':
            create_database(_db.engine.url)
        _db.create_all()

    yield _db

    # Explicitly close DB connection
    _db.session.close()
    _db.drop_all()


@pytest.yield_fixture()
def client(app):
    """Get test client."""
    with app.test_client() as client:
        print(app.url_map)
        yield client


@pytest.fixture(scope='module')
def app_config(app_config):
    """Customize application configuration."""
    app_config[
        'FILES_REST_STORAGE_FACTORY'] = 'oarepo_s3.storage.s3_storage_factory'
    app_config['S3_ENDPOINT_URL'] = None
    app_config['S3_CLIENT'] = 'tests.conftest.MockedS3Client'
    app_config['S3_ACCESS_KEY_ID'] = 'test'
    app_config['S3_SECRECT_ACCESS_KEY'] = 'test'
    app_config['FILES_REST_MULTIPART_CHUNKSIZE_MIN'] = 1024 * 1024 * 6
    # Endpoint with draft files support
    app_config['RECORDS_DRAFT_ENDPOINTS'] = {
        'recid': {
            'draft': 'drecid',
            'pid_type': 'recid',
            'pid_minter': 'recid',
            'pid_fetcher': 'recid',
            'record_class': 'tests.conftest:TestRecord',
            'record_serializers': {
                'application/json': (),
            },
            'search_serializers': {
                'application/json': (),
            },
            'search_type': None,
            'search_index': None,
            'indexer_class': TestIndexer,
            'list_route': '/records/',
            'item_route': '/records/<pid(recid, '
                          'record_class="invenio_records_files.api.Record"'
                          '):pid_value>',
        },
        'drecid': {
            'create_permission_factory_imp': allow_all,
            'delete_permission_factory_imp': allow_all,
            'update_permission_factory_imp': allow_all,
            'files': {
                'put_file_factory': allow_all,
                'get_file_factory': allow_all,
                'delete_file_factory': allow_all
            }
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
def draft_config(app_config):
    """Draft endpoints configuration."""
    app_config['RECORDS_DRAFT_ENDPOINTS'] = \
        app_config['RECORDS_REST_ENDPOINTS']
    app_config['RECORDS_DRAFT_ENDPOINTS'].update(
        dict(
            recid=dict(
                draft='drecid'
            ),
            drecid=dict(

            )
        ))
    app_config['RECORDS_REST_ENDPOINTS'] = {}
    return app_config


@pytest.fixture()
def prepare_es(app, db):
    """Prepare ES indices."""
    return


@pytest.fixture()
def draft_app(app):
    """Drafts app fixture."""
    return app


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


@pytest.fixture
def draft_records_url(app):
    """Draft endpoint url."""
    return url_for('oarepo_records_rest.draft_records_list')


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
        ('README.rst', b'readme file')
    ]:
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
    return stream


@pytest.fixture(scope='function')
def record(app, db, s3_location):
    """Create a record."""
    record = {
        'title': 'fuu'
    }
    record = Record.create(record)
    record.commit()
    db.session.commit()
    return record


@pytest.fixture()
def draft_record(app, db, prepare_es, s3_location):
    """Testing draft-enabled record."""
    draft_uuid = uuid.uuid4()
    data = {
        'title': 'blah',
        # '$schema': TestRecord.PREFERRED_SCHEMA,
        'id': '1'
    }
    PersistentIdentifier.create(
        pid_type='drecid', pid_value='1', status=PIDStatus.REGISTERED,
        object_type='rec', object_uuid=draft_uuid
    )
    rec = Record.create(data, id_=draft_uuid)
    return rec
