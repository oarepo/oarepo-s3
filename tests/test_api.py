# -*- coding: utf-8 -*-
#
# Copyright (C) 2018, 2019, 2020 Esteban J. G. Gabancho.
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""API tests."""

from __future__ import absolute_import, print_function

import flask
from flask import request, url_for
from werkzeug.datastructures import ImmutableMultiDict

from oarepo_s3.api import MultipartUploadStatus, multipart_uploader


def test_multipart_uploader(app, record, client):
    """Test multipart uploader."""
    fsize = 1024 * 1024 * 512
    files = record.files
    request.args = ImmutableMultiDict({'size': fsize, 'multipart': True})

    def _resolver(name, **kwargs):
        return url_for(
            'oarepo_records_draft.' + name.format(endpoint='drecid'),
            pid_value=1, **kwargs, _external=True)

    res = multipart_uploader(record=record, key='test', files=files,
                             pid=None, endpoint=None, request=request,
                             resolver=_resolver)
    assert res is not None
    assert callable(res)

    file_rec = files['test']
    file_rec['testparam'] = 'test'

    response = res()
    assert response['testparam'] == 'test'
    assert response.get('multipart_upload', None) is not None
    assert response['multipart_upload']['complete_url'] == \
        _resolver('{endpoint}_upload_complete', key='test')
    assert response['multipart_upload']['abort_url'] == \
        _resolver('{endpoint}_upload_abort', key='test')

    multi = response['multipart_upload']
    assert isinstance(response, dict)
    assert multi['bucket'] == 'test_invenio_s3'
    assert multi['num_chunks'] == 33
    assert multi['chunk_size'] == 16777216
    assert len(multi['parts_url']) == 33
    assert multi['status'] == MultipartUploadStatus.IN_PROGRESS
    assert isinstance(multi['upload_id'], str)

    assert file_rec.get('multipart_upload', None) is not None
