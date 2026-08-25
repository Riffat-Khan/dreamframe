"""Dream journal HTTP endpoints — thin wrappers around views."""

from app.auth.decorators import login_required
from app.dreams import bp
from app.dreams import views


@bp.get("/")
@login_required
def home():
    return views.home()


@bp.post("/dreams")
@login_required
def create_dream():
    return views.create_dream()


@bp.get("/journal")
@login_required
def journal():
    return views.journal()


@bp.get("/dreams/<int:dream_id>")
@login_required
def dream_detail(dream_id: int):
    return views.dream_detail(dream_id)


@bp.get("/dreams/<int:dream_id>/postcard")
@login_required
def dream_postcard(dream_id: int):
    return views.dream_postcard(dream_id)


@bp.get("/dreams/<int:dream_id>/postcard.svg")
@login_required
def dream_postcard_svg(dream_id: int):
    return views.dream_postcard_svg(dream_id)


@bp.get("/dreams/<int:dream_id>/edit")
@login_required
def edit_dream(dream_id: int):
    return views.edit_dream(dream_id)


@bp.post("/dreams/<int:dream_id>/edit")
@login_required
def update_dream(dream_id: int):
    return views.update_dream(dream_id)


@bp.post("/dreams/<int:dream_id>/regenerate")
@login_required
def regenerate_dream(dream_id: int):
    return views.regenerate_dream(dream_id)


@bp.post("/dreams/<int:dream_id>/regenerate-images")
@login_required
def regenerate_images(dream_id: int):
    return views.regenerate_images(dream_id)


@bp.post("/dreams/<int:dream_id>/panels/<int:panel_number>/image")
@login_required
def generate_panel_image(dream_id: int, panel_number: int):
    return views.generate_panel_image(dream_id, panel_number)


@bp.post("/dreams/<int:dream_id>/delete")
@login_required
def delete_dream(dream_id: int):
    return views.delete_dream(dream_id)
