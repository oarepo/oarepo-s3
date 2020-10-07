# -*- coding: utf-8 -*-
#
# Copyright (C) 2018, 2019, 2020 Esteban J. G. Gabancho.
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""Drafts integration tests."""
from mock import patch
from oarepo_records_draft import current_drafts

from tests.utils import draft_entrypoints


@patch('pkg_resources.iter_entry_points', draft_entrypoints)
def test_draft_integration(app, draft_record, client):
    """Test integration with invenio records draft library."""
    fsize = 1024 * 1024 * 200

    resp = client.post(
        '/draft/records/1/files?multipart=True',
        content_type='application/x-www-form-urlencoded',
        data={
            'key': 'test.txt',
            'multipart_content_type': 'text/plain',
            'size': fsize
        })
    assert resp.status_code == 400
    assert resp.json is None
