# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 CESNET
#
# oarepo-s3 is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""Pytest helpers."""

import flask
from flask import current_app
from flask_login import current_user
from flask_principal import Identity, RoleNeed, UserNeed, identity_changed, \
    identity_loaded
from invenio_access import authenticated_user


def set_identity(u):
    """Sets identity in flask.g to the user."""
    identity = Identity(u.id)
    identity_changed.send(current_app._get_current_object(), identity=identity)
    assert flask.g.identity.id == u.id


@identity_loaded.connect
def identity_loaded_callback(sender, identity=None, **kwargs):
    """Callback for identity_loaded signal."""
    print('Identity loaded', identity, current_user)
    if not current_user.is_authenticated:
        return

    identity.provides.add(authenticated_user)
    identity.provides.add(UserNeed(current_user.id))
    for r in current_user.roles:
        identity.provides.add(RoleNeed(r.name))
