from flask import Blueprint

bp = Blueprint("auth", __name__)

from app.auth import routes as auth_routes  # noqa: E402,F401
from app.auth.decorators import login_required  # noqa: E402,F401
