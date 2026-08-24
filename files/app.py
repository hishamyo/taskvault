"""TaskVault — a task management web app with private user accounts."""

import os
import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

DATABASE = os.environ.get("DATABASE_PATH", "taskvault.db")

PRIORITIES = ("low", "normal", "high")


# ---------------------------------------------------------------- database


def get_db():
    """Return a per-request database connection."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    title      TEXT NOT NULL,
    notes      TEXT NOT NULL DEFAULT '',
    due_date   TEXT,
    priority   TEXT NOT NULL DEFAULT 'normal',
    completed  INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id);
"""


def init_db():
    """Create tables and seed a demo account if the database is empty."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    existing = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    if existing == 0:
        seed_demo(conn)

    conn.commit()
    conn.close()


def seed_demo(conn):
    """Insert a demo account so the live site never looks empty."""
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        ("demo", generate_password_hash("demo123"), now),
    )
    uid = cur.lastrowid

    samples = [
        ("Finish CCNA subnetting chapter", "Sections 4.2 through 4.6, plus the lab.", 3, "high", 0),
        ("Deploy portfolio to Render", "Add gunicorn, push, connect repo.", 1, "high", 0),
        ("Review pull request from Amine", "Focus on the auth changes.", 0, "normal", 0),
        ("Write README for automation dashboard", "Include a screenshot and setup steps.", 6, "normal", 0),
        ("Renew library card", "", 14, "low", 0),
        ("Back up project database", "Weekly, every Sunday.", -1, "normal", 1),
        ("Book dentist appointment", "", -4, "low", 1),
    ]

    for title, notes, offset, priority, done in samples:
        due = date.fromordinal(date.today().toordinal() + offset).isoformat()
        conn.execute(
            """INSERT INTO tasks
               (user_id, title, notes, due_date, priority, completed, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (uid, title, notes, due, priority, done, now),
        )


# ------------------------------------------------------------------- auth


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_user():
    return {"current_user": session.get("username")}


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if len(username) < 3:
            flash("Username needs at least 3 characters.", "error")
        elif len(password) < 6:
            flash("Password needs at least 6 characters.", "error")
        elif password != confirm:
            flash("The two passwords do not match.", "error")
        else:
            db = get_db()
            taken = db.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if taken:
                flash("That username is already taken.", "error")
            else:
                cur = db.execute(
                    "INSERT INTO users (username, password_hash, created_at) "
                    "VALUES (?, ?, ?)",
                    (
                        username,
                        generate_password_hash(password),
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
                db.commit()
                session.clear()
                session["user_id"] = cur.lastrowid
                session["username"] = username
                return redirect(url_for("index"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        row = get_db().execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if row and check_password_hash(row["password_hash"], password):
            session.clear()
            session["user_id"] = row["id"]
            session["username"] = row["username"]
            return redirect(url_for("index"))

        flash("That username and password do not match a record.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------------------------------------------------------ tasks


@app.route("/")
@login_required
def index():
    view = request.args.get("view", "active")
    query = "SELECT * FROM tasks WHERE user_id = ?"
    params = [session["user_id"]]

    if view == "active":
        query += " AND completed = 0"
    elif view == "done":
        query += " AND completed = 1"

    query += """ ORDER BY completed ASC,
                 CASE WHEN due_date IS NULL OR due_date = '' THEN 1 ELSE 0 END,
                 due_date ASC, id DESC"""

    tasks = get_db().execute(query, params).fetchall()

    counts = get_db().execute(
        """SELECT
             COUNT(*) AS total,
             SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) AS active,
             SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS done
           FROM tasks WHERE user_id = ?""",
        (session["user_id"],),
    ).fetchone()

    return render_template(
        "index.html",
        tasks=tasks,
        view=view,
        counts=counts,
        today=date.today().isoformat(),
        priorities=PRIORITIES,
    )


@app.route("/tasks/add", methods=["POST"])
@login_required
def add_task():
    title = request.form.get("title", "").strip()
    if not title:
        flash("A task needs a title.", "error")
        return redirect(url_for("index", view=request.form.get("view", "active")))

    priority = request.form.get("priority", "normal")
    if priority not in PRIORITIES:
        priority = "normal"

    db = get_db()
    db.execute(
        """INSERT INTO tasks (user_id, title, notes, due_date, priority, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            session["user_id"],
            title[:200],
            request.form.get("notes", "").strip()[:1000],
            request.form.get("due_date") or None,
            priority,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    db.commit()
    return redirect(url_for("index", view=request.form.get("view", "active")))


@app.route("/tasks/<int:task_id>/toggle", methods=["POST"])
@login_required
def toggle_task(task_id):
    db = get_db()
    db.execute(
        "UPDATE tasks SET completed = 1 - completed WHERE id = ? AND user_id = ?",
        (task_id, session["user_id"]),
    )
    db.commit()
    return redirect(url_for("index", view=request.form.get("view", "active")))


@app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    db = get_db()
    task = db.execute(
        "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, session["user_id"]),
    ).fetchone()

    if task is None:
        flash("That task is not in your vault.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("A task needs a title.", "error")
        else:
            priority = request.form.get("priority", "normal")
            if priority not in PRIORITIES:
                priority = "normal"
            db.execute(
                """UPDATE tasks SET title = ?, notes = ?, due_date = ?, priority = ?
                   WHERE id = ? AND user_id = ?""",
                (
                    title[:200],
                    request.form.get("notes", "").strip()[:1000],
                    request.form.get("due_date") or None,
                    priority,
                    task_id,
                    session["user_id"],
                ),
            )
            db.commit()
            return redirect(url_for("index"))

    return render_template("edit.html", task=task, priorities=PRIORITIES)


@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    db = get_db()
    db.execute(
        "DELETE FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, session["user_id"]),
    )
    db.commit()
    return redirect(url_for("index", view=request.form.get("view", "active")))


# --------------------------------------------------------------- filters


@app.template_filter("prettydate")
def prettydate(value):
    if not value:
        return "No due date"
    try:
        d = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return value
    delta = (d - date.today()).days
    if delta == 0:
        return "Due today"
    if delta == 1:
        return "Due tomorrow"
    if delta == -1:
        return "1 day overdue"
    if delta < 0:
        return f"{abs(delta)} days overdue"
    return d.strftime("%d %b %Y")


@app.template_filter("overdue")
def overdue(value):
    if not value:
        return False
    try:
        return datetime.strptime(value, "%Y-%m-%d").date() < date.today()
    except ValueError:
        return False


init_db()


if __name__ == "__main__":
    app.run(debug=True)
