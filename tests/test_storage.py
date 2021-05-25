# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 CESNET
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""Storage tests."""

from __future__ import absolute_import, print_function

from oarepo_s3.api import MultipartUpload


def test_multipart_save(app, draft_record, s3storage, prepare_es):
    """Test on saving a multipart upload object on a Record."""
    fsize = 1024 * 1024 * 20
    files = draft_record.files

    mu = MultipartUpload(key='test',
                         base_uri=files.bucket.location.uri,
                         expires=3600,
                         size=fsize,
                         content_type='image/jpeg',
                         complete_url=None,
                         abort_url=None)

    files['test'] = mu
    file = files['test'].data

    assert file.get('checksum') is None
    assert file.get('size') == fsize
    assert all([key in mu.response.keys() for key in ['key', 'upload_id', 'bucket']])


def test_save(app, record, s3storage, prepare_es, generic_file):
    """Test the storage save method."""
    fsize = 1024 * 1024 * 20
    mu = MultipartUpload(key='test',
                         base_uri='s3://test_invenio_s3',
                         expires=3600,
                         size=fsize,
                         complete_url=None,
                         content_type='image/jpeg',
                         abort_url=None)

    res = s3storage.save(generic_file)
    assert res == (
        's3://test_invenio_s3/path/to/data',
        12, 'md5:f28427f7665f43a5d902733b655166f3')

    res = s3storage.save(mu)
    assert res == ('s3://test_invenio_s3/path/to/data', fsize, None)
