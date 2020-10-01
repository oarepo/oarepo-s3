# -*- coding: utf-8 -*-
#
# Copyright (C) 2018, 2019, 2020 Esteban J. G. Gabancho.
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""Storage tests."""

from __future__ import absolute_import, print_function

from oarepo_s3.api import MultipartUpload, multipart_uploader


def test_multipart_upload_save(create_app, record):
    mu = MultipartUpload('test', 3600)
    files = record.files

    files[mu.key] = mu
    file = files[mu.key].data
    assert file.get('checksum') is None
    assert file.get('size') == 0


def test_multipart_uploader(create_app, record):
    files = record.files
    res = multipart_uploader(record=record, key='test', files=files, pid=None, request=None,
                       resolver=lambda name, **kwargs: 'http://localhost/records/1/{}'.format(name))
    assert res is not None
    assert callable(res)
    # TODO: should be JSON string in the future
    assert isinstance(res(), MultipartUpload)
