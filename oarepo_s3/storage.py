# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 CESNET
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""S3 file storage interface."""
from __future__ import absolute_import, division, print_function

from functools import wraps

from invenio_files_rest.storage import pyfs_storage_factory
from s3fs.core import split_path

from invenio_s3 import S3FSFileStorage
from oarepo_s3.api import MultipartUpload
from oarepo_s3.proxies import current_s3


def pass_bucket(f):
    """Decorator to pass a bucket name from a fileurl."""

    @wraps(f)
    def inner(self, *args, **kwargs):
        bucket, _ = split_path(self.fileurl)
        return f(self, bucket=bucket, *args, **kwargs)

    return inner


class S3FileStorage(S3FSFileStorage):
    """File system storage using Amazon S3 API for accessing files
       and manage direct multi-part file uploads and downloads.
    """

    def __init__(self, fileurl, **kwargs):
        """Storage initialization."""
        super(S3FileStorage, self).__init__(fileurl, **kwargs)

    def save(self, *args, **kwargs):
        """Save incoming stream to S3 storage.

        If the incoming object is MultipartUpload, a direct S3
        multipart-upload flow is initiated instead.
        """
        if len(args) == 1 and isinstance(args[0], MultipartUpload):
            mu = args[0]
            mu.key = self.fileurl[len(mu.base_uri):].lstrip('/')
            self._size = mu.size
            return self.multipart_save(mu=mu)
        else:
            return super(S3FileStorage, self).save(*args, **kwargs)

    @pass_bucket
    def multipart_save(self, bucket, mu: MultipartUpload):
        """Initiate multipart-upload process on the S3 API.

        Initiates multipart-upload of an object and sets pre-signed
        urls on the multipartUpload to be used by the client to
        directly communicate with the S3 multipart APIs.
        """
        mu.response = current_s3.client.create_multipart_upload(bucket=bucket, key=mu.key, content_type=mu.content_type)
        assert mu.response['key'] == mu.key
        assert mu.response['bucket'] == bucket

        return self.fileurl, mu.size, None


def s3_storage_factory(**kwargs):
    """File storage factory for S3."""
    return pyfs_storage_factory(filestorage_class=S3FileStorage, **kwargs)
