from flask import Blueprint

bp = Blueprint("dreams", __name__)

from app.dreams import routes as dreams_routes  # noqa: E402,F401
