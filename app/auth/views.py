from flask import flash, g, redirect, render_template, request, session, url_for

from app.extensions import db
from app.models import DreamEntry, User


def register_get():
    if g.user:
        return redirect(url_for("dreams.home"))
    return render_template("auth/register.html")


def register_post():
    username = (request.form.get("username") or "").strip().lower()
    password = request.form.get("password") or ""
    confirm = request.form.get("confirm") or ""

    if len(username) < 3:
        flash("Username must be at least 3 characters.", "error")
        return redirect(url_for("auth.register"))
    if len(password) < 6:
        flash("Password must be at least 6 characters.", "error")
        return redirect(url_for("auth.register"))
    if password != confirm:
        flash("Passwords do not match.", "error")
        return redirect(url_for("auth.register"))
    if User.query.filter_by(username=username).first():
        flash("That username is already taken.", "error")
        return redirect(url_for("auth.register"))

    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    if User.query.count() == 1:
        orphaned = DreamEntry.query.filter(DreamEntry.user_id.is_(None)).all()
        for dream in orphaned:
            dream.user_id = user.id

    db.session.commit()
    session.clear()
    session["user_id"] = user.id
    flash(f"Welcome, {user.username}. Your journal is ready.", "info")
    return redirect(url_for("dreams.home"))


def login_get():
    if g.user:
        return redirect(url_for("dreams.home"))
    return render_template("auth/login.html")


def login_post():
    username = (request.form.get("username") or "").strip().lower()
    password = request.form.get("password") or ""
    next_url = request.args.get("next") or request.form.get("next") or url_for("dreams.home")

    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        flash("Invalid username or password.", "error")
        return redirect(url_for("auth.login", next=next_url))

    session.clear()
    session["user_id"] = user.id
    flash(f"Welcome back, {user.username}.", "info")
    if not str(next_url).startswith("/"):
        next_url = url_for("dreams.home")
    return redirect(next_url)


def logout_post():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("auth.login"))
