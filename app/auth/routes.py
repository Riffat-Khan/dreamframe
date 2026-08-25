"""Auth HTTP endpoints — thin wrappers around views."""

from flask import g, session

from app.auth import bp
from app.auth import views
from app.extensions import db
from app.models import User


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = db.session.get(User, user_id) if user_id else None


@bp.get("/register")
def register():
    return views.register_get()


@bp.post("/register")
def register_post():
    return views.register_post()


@bp.get("/login")
def login():
    return views.login_get()


@bp.post("/login")
def login_post():
    return views.login_post()


@bp.post("/logout")
def logout():
    return views.logout_post()
