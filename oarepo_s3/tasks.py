# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 CESNET
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""S3 file storage support tasks for Invenio."""
from datetime import datetime, timedelta

from celery import shared_task
from flask_sqlalchemy import BaseQuery
from invenio_db import db
from invenio_files_rest.models import ObjectVersionTag
from sqlalchemy.orm import lazyload

from oarepo_s3.constants import MULTIPART_EXPIRATION_TAG
from oarepo_s3.views import delete_file_object_version


@shared_task
def cleanup_expired_multipart_uploads():
    """Finds any expired file uploads and removes them."""
    expire_threshold = datetime.utcnow() - timedelta(days=1)
    expired = []

    def _delete_expired_upload(object_tag):
        object_version = object_tag.object_version
        bucket = object_version.bucket

        delete_file_object_version(bucket, object_version)
        return object_version

    with db.session.begin_nested():
        q = ObjectVersionTag.query \
            .options(lazyload('object_version')) \
            .filter_by(key=MULTIPART_EXPIRATION_TAG) \
            .filter(ObjectVersionTag.value < expire_threshold.isoformat())

        expired = [_delete_expired_upload(otag) for otag in q.all()]

    db.session.commit()

    return expired
