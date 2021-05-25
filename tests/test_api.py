# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 CESNET
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""API tests."""

from __future__ import absolute_import, print_function

import json

import flask
from flask import request, url_for
from werkzeug.datastructures import ImmutableMultiDict

from oarepo_s3.api import multipart_uploader
from oarepo_s3.constants import MULTIPART_CONFIG_TAG, MULTIPART_EXPIRATION_TAG


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
    print(response)
    assert 'uploadId' in response
    assert 'key' in response

    tags = file_rec.obj.get_tags()
    assert list(tags.keys()) == [MULTIPART_CONFIG_TAG,
                                 MULTIPART_EXPIRATION_TAG]
    assert json.loads(tags[MULTIPART_CONFIG_TAG]) is not None
