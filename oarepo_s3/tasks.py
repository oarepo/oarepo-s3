# -*- coding: utf-8 -*-
#
# Copyright (C) 2018, 2019, 2020 Esteban J. G. Gabancho.
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""S3 file storage support tasks for Invenio."""
from celery import shared_task
from invenio_records_files.api import FileObject


@shared_task
def cleanup_expired_multipart_uploads():
    """Finds any expired file uploads and removes them."""
    # TODO: TBD
    pass
