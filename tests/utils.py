# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 CESNET
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""Test utils."""
import pkg_resources


def draft_entrypoints(app, group=None, name=None):
    """Additional draft entrypoints."""
    d = pkg_resources.Distribution()
    s3_uploader = pkg_resources.EntryPoint.parse(
        'oarepo_s3 = oarepo_s3.api:multipart_uploader', dist=d)
    s3_actions = pkg_resources.EntryPoint.parse(
        'oarepo_s3 = oarepo_s3.views:multipart_actions', dist=d)

    data = {
        'oarepo_records_draft.uploaders': [s3_uploader],
        'oarepo_records_draft.extra_actions': [s3_actions]
    }

    names = data.keys() if name is None else [name]
    for key in names:
        for entry_point in data[key]:
            print(entry_point)
            yield entry_point
