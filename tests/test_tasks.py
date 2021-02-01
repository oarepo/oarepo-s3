# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 CESNET
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""Storage tests."""

from __future__ import absolute_import, print_function

from flask import request, url_for
from werkzeug.datastructures import ImmutableMultiDict

from oarepo_s3.api import multipart_uploader
from celery.contrib.pytest import celery_worker
from oarepo_s3.tasks import cleanup_expired_multipart_uploads


def test_cleanup_expired_multipart_uploads(app, draft_record, client, s3storage, prepare_es):
    """"Test expired uploads cleanup."""
    fsize = 1024 * 1024 * 512
    files = draft_record.files
    request.args = ImmutableMultiDict({'size': fsize, 'multipart': True})

    # Shift created expiration timestamp to 10 days back
    app.config['S3_MULTIPART_UPLOAD_EXPIRATION'] = - 60*60*24*10

    def _resolver(name, **kwargs):
        return url_for(
            'oarepo_records_draft.' + name.format(endpoint='drecid'),
            pid_value=1, **kwargs, _external=True)

    res = multipart_uploader(record=draft_record, key='test', files=files,
                             pid=None, endpoint=None, request=request,
                             resolver=_resolver)
    res()
    assert 'test' in files

    expired = cleanup_expired_multipart_uploads()
    assert len(expired) == 1
    assert expired[0].key == 'test'
    assert 'test' not in files
