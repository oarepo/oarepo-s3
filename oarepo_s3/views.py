# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 CESNET
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""S3 file storage support for Invenio.

To use this module together with Invenio-Files-Rest there are a few things you
need to keep in mind.

The storage factory configuration variable, ``FILES_REST_STORAGE_FACTORY``
needs to be set to ``'oarepo_s3.s3fs_storage_factory'`` importable string.

We think the best way to use this module is to have one `Localtion
<https://invenio-files-rest.readthedocs.io/en/latest/api.html#module-invenio_files_rest.models>`_
for each S3 bucket. This is just for simplicity, it can used however needed.

When creating a new location which will use the S3 API, the URI needs to start
with ``s3://``, for example
``invenio files location s3_default s3://my-bucket --default`` will
create a new location, set it as default location for your instance and use the
bucket ``my-bucket``. For more information about this command check
`Invenio-Files-Rest <https://invenio-files-rest.readthedocs.io/en/latest/>`_
documentation.

Then, there are a few configuration variables that need to be set on your
instance, like the endpoint, the access key and the secret access key, see a
more detailed description in :any:`configuration`.

.. note::

  This module doesn't create S3 buckets automatically, so before starting they
  need to be created.

  You might also want to set the correct `CORS configuration
  <https://docs.aws.amazon.com/AmazonS3/latest/dev/cors.html>`_  so files can
  be used by your interface for things like previewing a PDF with some
  Javascript library.

"""
import json
from functools import wraps

from flask import abort, jsonify, request
from flask.views import MethodView
from invenio_db import db
from invenio_files_rest.models import ObjectVersion, ObjectVersionTag
from invenio_files_rest.signals import file_deleted
from invenio_files_rest.tasks import remove_file_data
from invenio_records_rest.errors import PIDResolveRESTError
from invenio_rest import csrf
from sqlalchemy.exc import SQLAlchemyError
from webargs import fields
from webargs.flaskparser import use_kwargs

from oarepo_s3.constants import MULTIPART_CONFIG_TAG, MULTIPART_EXPIRATION_TAG
from oarepo_s3.proxies import current_s3
from oarepo_s3.signals import after_upload_abort, after_upload_complete, \
    before_upload_abort, before_upload_complete

multipart_complete_args = {
    'parts': fields.List(
        fields.Dict,
        locations=('json', 'form'))
}


def pass_locked_record(f):
    """Decorator to retrieve persistent identifier and record.

    This decorator will resolve the ``pid_value`` parameter from the route
    pattern and resolve it to a PID and a record, which are then available in
    the decorated function as ``pid`` and ``record`` kwargs respectively.
    """

    @wraps(f)
    def inner(self, pid_value, *args, **kwargs):
        try:
            pid, record = request.view_args['pid_value'].data
            record = lock_record(record)
            return f(self, pid=pid, record=record, *args, **kwargs)
        except SQLAlchemyError:
            raise PIDResolveRESTError(pid_value)

    return inner


def pass_file_rec(f):
    """Decorator to retrieve a FileObject
       given by key from record FilesIterator.
    """

    @wraps(f)
    def inner(self, pid, record, key, *args, **kwargs):
        files = record.files
        try:
            file_rec = files[key]
        except KeyError:
            abort(404, 'upload not found')
        return f(self, pid=pid, record=record, key=key,
                 files=files, file_rec=file_rec, *args, **kwargs)

    return inner


def pass_multipart_config(f):
    """Decorator to retrieve a multipart upload
       configuration from FileObject tags.
    """

    @wraps(f)
    def inner(self, pid, record, key, files, file_rec, *args, **kwargs):
        mc = file_rec.obj.get_tags().get(MULTIPART_CONFIG_TAG, None)
        if not mc:
            abort(400, 'resource is not a multipart upload')

        mc = json.loads(mc)
        return f(self, pid=pid, record=record, key=key, files=files,
                 file_rec=file_rec, multipart_config=mc, *args, **kwargs)

    return inner


def delete_file_object_version(bucket, obj):
    """Permanently delete a specific object version."""
    obj.remove()
    # Set newest object as head
    if obj.is_head:
        latest = ObjectVersion.get_versions(obj.bucket,
                                            obj.key,
                                            desc=True).first()
        if latest:
            latest.is_head = True

    if obj.file_id:
        remove_file_data.delay(str(obj.file_id))

    file_deleted.send(obj)


def lock_record(record):
    # lock the record in case of multiple uploads to the same record
    cls = type(record)
    obj = cls.model_cls.query.filter_by(id=record.id). \
        filter(cls.model_cls.json != None).with_for_update().one()
    db.session.expire(obj)
    return cls.get_record(record.id)


class MultipartUploadCompleteResource(MethodView):
    """Complete multipart upload method view."""
    view_name = '{endpoint}_upload_complete'

    @pass_locked_record
    @pass_file_rec
    @pass_multipart_config
    @use_kwargs(multipart_complete_args)
    def post(self, pid, record, key, files, file_rec, multipart_config, upload_id, parts):
        if multipart_config['upload_id'] != upload_id:
            abort(404)

        before_upload_complete.send(file_rec,
                                    record=record,
                                    file=file_rec,
                                    multipart_config=multipart_config)

        res = current_s3.client.complete_multipart_upload(bucket=multipart_config['bucket'],
                                                          key=multipart_config['key'],
                                                          upload_id=upload_id,
                                                          parts=parts)

        with db.session.begin_nested():
            ObjectVersionTag.delete(file_rec.obj, MULTIPART_CONFIG_TAG)
            ObjectVersionTag.delete(file_rec.obj, MULTIPART_EXPIRATION_TAG)

            etag = 'etag:{}'.format(res['ETag'])
            file_rec.obj.file.checksum = etag
            file_rec['checksum'] = etag

            after_upload_complete.send(file_rec, record=record, file=file_rec, files=files)

            files.flush()
            record.commit()

        db.session.commit()
        return jsonify({'location': file_rec.data['url']})


class MultipartUploadAbortResource(MethodView):
    """Cancel a multipart upload method view."""
    view_name = '{endpoint}_upload_abort'

    @pass_locked_record
    @pass_file_rec
    @pass_multipart_config
    def delete(self, pid, record, files, file_rec, multipart_config, key, upload_id):
        if multipart_config['upload_id'] != upload_id:
            abort(404)

        before_upload_abort.send(file_rec,
                                 record=record,
                                 file=file_rec,
                                 multipart_config=multipart_config)

        res = current_s3.client.abort_multipart_upload(
            bucket=multipart_config['bucket'],
            key=multipart_config['key'],
            upload_id=upload_id)

        with db.session.begin_nested():
            delete_file_object_version(file_rec.bucket, file_rec.obj)
            head = ObjectVersion.get(file_rec.bucket, key)
            if not head:
                del files.filesmap[key]

            files.flush()
            record.commit()

        db.session.commit()

        after_upload_abort.send(file_rec, record=record, file=file_rec)

        return jsonify({})


class UploadedPartsResource(MethodView):
    """Resource for uploaded parts in a multipart upload."""
    view_name = '{endpoint}_uploaded_parts'

    @pass_locked_record
    @pass_file_rec
    @pass_multipart_config
    def get(self, pid, record, files, file_rec, multipart_config, key, upload_id):
        if multipart_config['upload_id'] != upload_id:
            abort(404)

        parts = current_s3.client.get_uploaded_parts(bucket=multipart_config['bucket'],
                                                     key=multipart_config['key'],
                                                     upload_id=upload_id)

        return jsonify(parts)


class PresignedPartResource(MethodView):
    """Presigned Part Upload URL Resource."""
    view_name = '{endpoint}_presigned_part'

    @pass_locked_record
    @pass_file_rec
    @pass_multipart_config
    def get(self, pid, record, files, file_rec, multipart_config, key, upload_id, part_ids):
        part_numbers = []
        presigned_urls = []
        parts = part_ids.split(',')

        if multipart_config['upload_id'] != upload_id:
            abort(404)

        try:
            part_numbers = map(int, parts)
        except ValueError:
            abort(400, 'the part numbers must be a number between 1 and 10000')

        for part_num in part_numbers:
            presigned_urls.append({part_num: current_s3.client.sign_part_upload(bucket=multipart_config['bucket'],
                                                                     key=multipart_config['key'],
                                                                     upload_id=upload_id,
                                                                     part_num=part_num)})

        return jsonify({'presignedUrls': presigned_urls})


def multipart_actions(code, files, rest_endpoint, extra, is_draft):
    # decide if view should be created on this
    # resource and return blueprint mapping
    # rest path -> view
    return {
        'files/<key>/<upload_id>/<part_ids>/presigned':
            csrf.exempt(PresignedPartResource.as_view(
                PresignedPartResource.view_name.format(endpoint=code)
            )),
        'files/<key>/<upload_id>/parts':
            csrf.exempt(UploadedPartsResource.as_view(
                UploadedPartsResource.view_name.format(endpoint=code)
            )),
        'files/<key>/<upload_id>/complete':
            csrf.exempt(MultipartUploadCompleteResource.as_view(
                MultipartUploadCompleteResource.view_name.format(endpoint=code)
            )),
        'files/<key>/<upload_id>/abort':
            csrf.exempt(MultipartUploadAbortResource.as_view(
                MultipartUploadAbortResource.view_name.format(endpoint=code)
            ))
    }
