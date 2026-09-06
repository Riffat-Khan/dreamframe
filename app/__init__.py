from flask import Flask
from sqlalchemy import inspect, text

from app.config import BASE_DIR, Config
from app.extensions import db


def _ensure_column(table: str, column: str, ddl: str) -> None:
    inspector = inspect(db.engine)
    if table not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns(table)}
    if column in columns:
        return
    with db.engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    from app.auth import bp as auth_bp
    from app.dreams import bp as dreams_bp
    from app.map import bp as map_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dreams_bp)
    app.register_blueprint(map_bp)

    with app.app_context():
        from app import models  # noqa: F401

        db.create_all()
        _ensure_column("dream_entries", "user_id", "user_id INTEGER")
        _ensure_column("dream_analyses", "symbols_json", "symbols_json TEXT DEFAULT '[]'")

    # Initialize the async task queue
    from app.services.task_queue import get_task_queue
    queue = get_task_queue()
    queue.set_app(app)

    return app
