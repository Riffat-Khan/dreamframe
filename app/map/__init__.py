from flask import Blueprint

bp = Blueprint("map", __name__, url_prefix="")

from app.map import routes as map_routes  # noqa: E402,F401
