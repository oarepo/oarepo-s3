# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 CESNET
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""S3 file storage support tasks for Invenio."""

from blinker import Namespace

_signals = Namespace()


before_upload_complete = _signals.signal('before_upload_complete')
"""
A signal being sent just before a multipart upload is completed

:param record: the record the file is associated with
:param file: FileInstance instance of file being completed
:param parts: list of uploaded file parts
:param multipart_config: dict containing the multipart upload session config
"""

after_upload_complete = _signals.signal('after_upload_complete')
"""
A notification called after the multipart upload is completed

:param record: the record the file is associated with
:param file: FileInstance instance of the uploaded file
"""

before_upload_abort = _signals.signal('before_upload_abort')
"""
A notification called just before a multipart is aborted

:param record: the record the file is associated with
:param file: FileInstance instance of the aborted file
:param multipart_config: dict containing the multipart upload session config
"""

after_upload_abort = _signals.signal('after_upload_abort')
"""
A notification called after a multipart upload gets aborted

:param record: the record the file is associated with
:param file: FileInstance instance of the aborted file
"""
