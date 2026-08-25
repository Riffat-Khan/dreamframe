from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    dreams = db.relationship("DreamEntry", back_populates="owner", cascade="all, delete-orphan")
    symbols = db.relationship("DreamSymbol", back_populates="owner", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class DreamEntry(db.Model):
    __tablename__ = "dream_entries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    original_text = db.Column(db.Text, nullable=False)
    mood = db.Column(db.String(64), nullable=True)
    style = db.Column(db.String(32), nullable=False, default="soft")
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    owner = db.relationship("User", back_populates="dreams")
    analysis = db.relationship(
        "DreamAnalysis",
        back_populates="dream",
        uselist=False,
        cascade="all, delete-orphan",
    )
    symbol_links = db.relationship(
        "DreamSymbolLink",
        back_populates="dream",
        cascade="all, delete-orphan",
    )


class DreamAnalysis(db.Model):
    __tablename__ = "dream_analyses"

    id = db.Column(db.Integer, primary_key=True)
    dream_id = db.Column(db.Integer, db.ForeignKey("dream_entries.id", ondelete="CASCADE"), unique=True)
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    themes_json = db.Column(db.Text, nullable=False, default="[]")
    emotions_json = db.Column(db.Text, nullable=False, default="[]")
    panels_json = db.Column(db.Text, nullable=False, default="[]")
    symbols_json = db.Column(db.Text, nullable=False, default="[]")

    dream = db.relationship("DreamEntry", back_populates="analysis")


class DreamSymbol(db.Model):
    __tablename__ = "dream_symbols"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name_key = db.Column(db.String(120), nullable=False, index=True)
    display_name = db.Column(db.String(120), nullable=False)
    kind = db.Column(db.String(32), nullable=False, default="motif")
    mention_count = db.Column(db.Integer, nullable=False, default=0)
    last_seen_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    owner = db.relationship("User", back_populates="symbols")
    links = db.relationship(
        "DreamSymbolLink",
        back_populates="symbol",
        cascade="all, delete-orphan",
    )

    __table_args__ = (db.UniqueConstraint("user_id", "name_key", name="uq_user_symbol"),)


class DreamSymbolLink(db.Model):
    __tablename__ = "dream_symbol_links"

    id = db.Column(db.Integer, primary_key=True)
    symbol_id = db.Column(db.Integer, db.ForeignKey("dream_symbols.id", ondelete="CASCADE"), nullable=False)
    dream_id = db.Column(db.Integer, db.ForeignKey("dream_entries.id", ondelete="CASCADE"), nullable=False)

    symbol = db.relationship("DreamSymbol", back_populates="links")
    dream = db.relationship("DreamEntry", back_populates="symbol_links")

    __table_args__ = (db.UniqueConstraint("symbol_id", "dream_id", name="uq_symbol_dream"),)
