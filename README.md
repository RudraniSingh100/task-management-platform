# Secure Task Management Platform

A Flask backend project upgraded from a basic todo API into a secure task management platform with JWT authentication, PostgreSQL persistence, task deadlines, priority workflows, dashboard metrics, API search/filtering, Docker support, and a simple recruiter-facing UI.

## Features

- JWT login/register flow with access and refresh token generation.
- User-scoped task lists and tasks protected by bearer-token authentication.
- Task deadlines using `due_date`, reminder timestamps, and overdue dashboard tracking.
- Priority levels: `low`, `medium`, and `high`.
- Search and filtering by text, priority, completion state, overdue state, and due-date range.
- User dashboard with total, pending, completed, overdue, and high-priority task counts.
- Modular Flask Blueprints for API and UI routes.
- PostgreSQL-ready schema with Alembic migrations.
- Docker, Render, and Procfile deployment configuration.
- Postman collection for API testing.

## Tech Stack

- **Backend:** Flask, Flask-SQLAlchemy, Pydantic
- **Authentication:** JWT with `python-jose`, bcrypt password hashing
- **Database:** PostgreSQL, Alembic migrations
- **Deployment:** Docker, Gunicorn, Render/Railway-compatible `DATABASE_URL`
- **Testing workflow:** Postman collection in `docs/postman_collection.json`
- **Frontend:** Flask templates, vanilla JavaScript, CSS

## Screenshots

Dashboard and task filtering UI:

![Dashboard screenshot](secure_task_mgmt/docs/screenshots/dashboard.png)

Add the final deployed login and mobile screenshots before publishing if you want a fuller gallery.

## Folder Structure

```text
.
├── alembic/                  # Database migrations
├── docs/
│   └── postman_collection.json
├── todo_app/
│   ├── static/               # Browser UI assets
│   ├── templates/            # Flask-rendered UI
│   ├── __init__.py           # App setup and Blueprint registration
│   ├── config.py             # Environment-driven configuration
│   ├── decorators.py         # Auth middleware
│   ├── jwt.py                # Token creation/validation helpers
│   ├── models.py             # SQLAlchemy models
│   ├── routers.py            # REST API Blueprint
│   └── schemas.py            # Pydantic request/response schemas
├── Dockerfile
├── docker-compose.yml
├── Procfile
├── render.yaml
└── requirements.txt
```

## Local Setup With Docker

1. Create your environment file:

```bash
cp .env.example .env
```

2. Start PostgreSQL and the Flask app:

```bash
docker compose up -d --build
```

3. Open the UI:

```text
http://localhost:8080
```

## Local Setup Without Docker

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Export database settings or a full `DATABASE_URL`:

```bash
export DATABASE_URL=postgresql://todo_user:todo_pass@localhost:5432/todo_db
export SECRET_KEY=replace-with-a-long-random-secret
```

3. Run migrations and start the app:

```bash
alembic upgrade head
python -m flask --app todo_app run --port 8080
```

## API Endpoints

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/register` | No | Create a user account |
| `POST` | `/login` | No | Return access and refresh tokens |
| `POST` | `/refresh` | No | Exchange a refresh token for a new access token |
| `GET` | `/dashboard` | Yes | Return user task metrics |
| `GET` | `/tasks` | Yes | Search/filter all user tasks |
| `GET` | `/tasklist` | Yes | List user task lists |
| `POST` | `/tasklist` | Yes | Create a task list |
| `PATCH` | `/tasklist` | Yes | Reorder task lists |
| `GET` | `/tasklist/<tasklist_id>` | Yes | Get a task list |
| `PUT` | `/tasklist/<tasklist_id>` | Yes | Update a task list |
| `DELETE` | `/tasklist/<tasklist_id>` | Yes | Delete a task list |
| `GET` | `/tasklist/<tasklist_id>/tasks` | Yes | List tasks with filters |
| `POST` | `/tasklist/<tasklist_id>/tasks` | Yes | Create a task |
| `PATCH` | `/tasklist/<tasklist_id>/tasks` | Yes | Reorder tasks |
| `GET` | `/tasklist/<tasklist_id>/tasks/<task_id>` | Yes | Get a task |
| `PATCH` | `/tasklist/<tasklist_id>/tasks/<task_id>` | Yes | Update title, deadline, priority, completion |
| `DELETE` | `/tasklist/<tasklist_id>/tasks/<task_id>` | Yes | Delete a task |
| `POST` | `/tasklist/<tasklist_id>/tasks/<task_id>/steps` | Yes | Add a step |
| `PUT` | `/tasklist/<tasklist_id>/tasks/<task_id>/steps/<step_id>` | Yes | Update a step |
| `DELETE` | `/tasklist/<tasklist_id>/tasks/<task_id>/steps/<step_id>` | Yes | Delete a step |

### Task Filtering Query Params

Use these with `/tasks` or `/tasklist/<tasklist_id>/tasks`:

```text
q=flask
priority=high
is_completed=false
overdue=true
due_before=2026-05-20T10:00:00Z
due_after=2026-05-13T10:00:00Z
```

## Example Task Payload

```json
{
  "title": "Submit backend internship project",
  "description": "Attach deployed app, GitHub repo, and README",
  "priority": "high",
  "due_date": "2026-05-20T10:00:00Z",
  "reminder": null,
  "steps": [
    { "title": "Verify JWT login" },
    { "title": "Import Postman collection" }
  ]
}
```

## Deployment

### Render

1. Push this repo to GitHub.
2. Create a Render Blueprint from `render.yaml`, or create a Web Service manually.
3. Add a PostgreSQL database.
4. Set `DATABASE_URL` and `SECRET_KEY`.
5. Use this start command:

```bash
alembic upgrade head && gunicorn -w 4 -b 0.0.0.0:$PORT todo_app:app
```

### Railway

1. Create a Railway project from the GitHub repo.
2. Add PostgreSQL.
3. Set `DATABASE_URL` and `SECRET_KEY`.
4. Railway can use the `Procfile` command automatically.

Deployment link:

```text
Add your Render/Railway URL here after deployment.
```

## Postman Testing

Import `docs/postman_collection.json`, then run:

1. Register
2. Login
3. Create Task List
4. Create High Priority Task
5. Search Tasks
6. Complete Task
7. Dashboard

The login request stores `accessToken` as a collection variable for protected endpoints.

## Interview Notes

- **JWT authentication:** Login verifies the bcrypt-hashed password and returns signed access/refresh tokens.
- **Token lifecycle:** Access tokens are short-lived; refresh tokens last longer and can be used to issue a new access token.
- **Schema design:** Users own task lists; task lists own tasks; tasks own steps. Cascading deletes clean child records.
- **REST architecture:** Each resource has predictable CRUD endpoints with bearer-token protection.
- **Security practices:** Passwords are hashed, protected routes validate bearer tokens, and users can only query their own task data.
- **Scaling path:** Add pagination, background reminders, rate limiting, Redis token revocation, test coverage, and CI/CD.

## Resume Bullets

- Developed secure backend architecture using Flask, JWT authentication, PostgreSQL, and modular RESTful APIs.
- Implemented role-based task management with deadline tracking, prioritization, and optimized relational schema.
- Dockerized the application and configured production-ready Render/Railway deployment settings.
