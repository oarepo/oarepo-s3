# -*- coding: utf-8 -*-
#
# Copyright (C) 2018, 2019, 2020 Esteban J. G. Gabancho.
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""S3 file storage interface."""
from __future__ import absolute_import, division, print_function

from functools import partial, wraps

import s3fs
from flask import current_app
from invenio_files_rest.errors import StorageError
from invenio_files_rest.storage import PyFSFileStorage, pyfs_storage_factory
from invenio_s3 import S3FSFileStorage
from s3_client_lib.s3_client import S3Client
from s3_client_lib.s3_multipart_client import S3MultipartClient

from oarepo_s3.api import MultipartUpload
from oarepo_s3.utils import multipart_init_response_factory


def set_blocksize(f):
    """Decorator to set the correct block size according to file size."""
    @wraps(f)
    def inner(self, *args, **kwargs):
        size = kwargs.get('size', None)
        block_size = (
            size // current_app.config['S3_MAXIMUM_NUMBER_OF_PARTS']  # Integer
            if size
            else current_app.config['S3_DEFAULT_BLOCK_SIZE']
        )

        if block_size > self.block_size:
            self.block_size = block_size
        return f(self, *args, **kwargs)

    return inner


class S3FileStorage(S3FSFileStorage):
    """File system storage using Amazon S3 API for accessing files
       and manage direct multi-part file uploads and downloads.
    """
    def __init__(self, fileurl, **kwargs):
        """Storage initialization."""
        super(S3FileStorage, self).__init__(fileurl, **kwargs)

    def save(self, *args, **kwargs):
        if len(args) == 1 and isinstance(args[0], MultipartUpload):
            mu = args[0]
            # TODO: initialize multipart upload against S3 API and set result on mu
        return self.fileurl, 0, None


def s3_storage_factory(**kwargs):
    """File storage factory for S3."""
    return pyfs_storage_factory(filestorage_class=S3FileStorage, **kwargs)
