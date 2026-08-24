# TaskVault

A task management web application where every user gets a private, isolated task list.

**Live demo:** _add your Render URL here_
**Demo login:** username `demo` / password `demo123`

---

## What it does

TaskVault lets a user register an account, sign in, and manage their own tasks. Each task has a title, optional notes, a due date, and a priority level. Tasks can be edited, marked complete, reopened, or deleted, and filtered by status.

Every database query is scoped to the signed-in user's ID, so one account can never read or modify another account's data.

## Features

- User registration and sign-in with hashed passwords (Werkzeug PBKDF2)
- Session-based authentication with a `login_required` decorator on protected routes
- Full create, read, update, and delete for tasks
- Due dates with human-readable formatting ("Due today", "3 days overdue")
- Priority levels shown as a colour-coded edge on each record
- Filter views: open, filed, and all
- Per-user data isolation enforced at the query level
- Responsive layout that works down to mobile width

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3 |
| Framework | Flask |
| Templating | Jinja2 |
| Database | SQLite |
| Auth | Werkzeug security (password hashing) |
| Server | Gunicorn |
| Styling | Hand-written CSS |

## Project structure

```
taskvault/
├── app.py              # Routes, database access, auth
├── requirements.txt
├── Procfile
├── templates/
│   ├── layout.html     # Shared shell
│   ├── login.html
│   ├── register.html
│   ├── index.html      # Task list and composer
│   └── edit.html
└── static/
    └── styles.css
```

## Running locally

```bash
git clone https://github.com/YOUR_USERNAME/taskvault.git
cd taskvault

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` and sign in with `demo` / `demo123`, or create a new account.

The database file is created automatically on first run and seeded with a demo account so the app is never empty.

## Deploying to Render

1. Push this repository to GitHub
2. On Render: **New** → **Web Service** → connect the repository
3. Configure:
   - **Language:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
   - **Instance Type:** Free
4. Add an environment variable `SECRET_KEY` with a long random value
5. Deploy

> **Note on the free tier:** free instances sleep after 15 minutes of inactivity and lose any files written to disk. The SQLite database resets when this happens, and the app reseeds the demo account automatically. For persistent storage, attach a Render Postgres instance.

## Security notes

- Passwords are never stored in plain text
- All task queries filter on `user_id` from the session, not from user input
- Destructive routes accept `POST` only
- The secret key is read from an environment variable in production
- Input lengths are capped server-side

## Database schema

```sql
users (id, username UNIQUE, password_hash, created_at)
tasks (id, user_id → users.id, title, notes, due_date, priority, completed, created_at)
```

## Possible next steps

- Migrate from SQLite to PostgreSQL for persistent hosting
- Task categories or tags
- Search across titles and notes
- Email reminders for approaching due dates

---

Built by Hisham Yassir · [GitHub](https://github.com/hishamyo) · [LinkedIn](https://linkedin.com/in/hisham-yassir-a16869308)
