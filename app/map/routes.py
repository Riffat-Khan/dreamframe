"""Dream map HTTP endpoints — thin wrappers around views."""

from app.auth.decorators import login_required
from app.map import bp
from app.map import views


@bp.get("/map")
@login_required
def dream_map():
    return views.dream_map()


@bp.post("/map/rebuild")
@login_required
def rebuild_map():
    return views.rebuild_map()


@bp.get("/map/symbols/<int:symbol_id>")
@login_required
def symbol_detail(symbol_id: int):
    return views.symbol_detail(symbol_id)
