# -*- coding: utf-8 -*-
#
# Copyright (C) 2018, 2019, 2020 Esteban J. G. Gabancho.
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

    mu = MultipartUpload('test', 3600, fsize)

    files[mu.key] = mu
    file = files[mu.key].data

    assert file.get('checksum') is None
    assert file.get('size') == fsize
    assert all([key in mu.session.keys() for key in [
        'parts_url', 'chunk_size', 'upload_id', 'num_chunks', 'bucket']])
    assert len(mu.session['parts_url']) == int(mu.session['num_chunks'])


def test_save(app, record, s3storage, prepare_es, generic_file):
    """Test the storage save method."""
    fsize = 1024 * 1024 * 20
    mu = MultipartUpload('test', 3600, fsize)

    res = s3storage.save(generic_file)
    assert res == (
        's3://test_invenio_s3/path/to/data',
        12, 'md5:f28427f7665f43a5d902733b655166f3')

    res = s3storage.save(mu)
    assert res == ('s3://test_invenio_s3/path/to/data', fsize, None)
