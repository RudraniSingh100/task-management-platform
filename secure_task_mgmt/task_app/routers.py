from datetime import datetime

from flask import Blueprint, request
from pydantic import ValidationError
from pydantic.error_wrappers import ErrorWrapper
from sqlalchemy import case, or_
from sqlalchemy.orm import joinedload
from todo_app import db
from todo_app.decorators import auth_required
from todo_app.models import TaskList, Task, Step, User
from todo_app.exceptions import NotFoundException, BadRequestException
from todo_app.hash import get_password_hash, verify_password
from todo_app.jwt import create_token_pair, refresh_token_state
from todo_app.schemas import (
    TaskListScheme,
    TaskScheme,
    TaskListCreateScheme,
    TaskCreateScheme,
    TaskPartialUpdateSchema,
    UpdateOrderScheme,
    StepCreateScheme,
    StepScheme,
    UserRegister,
    UserLogin,
    User as UserSchema,
    DashboardStatsScheme,
)


api_bp = Blueprint("api", __name__)

GET = "GET"
POST = "POST"
PUT = "PUT"
PATCH = "PATCH"
DELETE = "DELETE"


def _parse_datetime_param(name: str):
    value = request.args.get(name)
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise BadRequestException(f"Invalid {name}. Use ISO-8601 datetime format.")


def _filtered_tasks_query(query):
    query = query.options(joinedload(Task.steps))

    q = request.args.get("q")
    priority = request.args.get("priority")
    is_completed = request.args.get("is_completed")
    overdue = request.args.get("overdue")
    due_before = _parse_datetime_param("due_before")
    due_after = _parse_datetime_param("due_after")

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(Task.title.ilike(like), Task.description.ilike(like)))

    if priority:
        if priority not in {"low", "medium", "high"}:
            raise BadRequestException("priority must be low, medium, or high")
        query = query.filter(Task.priority == priority)

    if is_completed is not None:
        query = query.filter(Task.is_completed == (is_completed.lower() == "true"))

    if overdue is not None and overdue.lower() == "true":
        query = query.filter(Task.is_completed.is_(False), Task.due_date < datetime.utcnow())

    if due_before:
        query = query.filter(Task.due_date <= due_before)

    if due_after:
        query = query.filter(Task.due_date >= due_after)

    priority_rank = case(
        (Task.priority == "high", 1),
        (Task.priority == "medium", 2),
        else_=3,
    )
    return query.order_by(priority_rank, Task.due_date.asc().nullslast(), Task.order.asc())


# ----------------- Login, Register views -------------------
@api_bp.route("/login", methods=[POST])
def login():
    data = UserLogin(**request.json)
    user = User.query.filter_by(email=data.email).first()

    if not user or not verify_password(data.password, user.password):
        raise BadRequestException("Incorrect email or password")

    token_pair = create_token_pair(user=UserSchema.from_orm(user))

    return {"access": token_pair.access.token, "refresh": token_pair.refresh.token}, 200


@api_bp.route("/refresh", methods=[POST])
def refresh():
    refresh_token = (request.json or {}).get("refresh")
    if not refresh_token:
        raise BadRequestException("Refresh token is required")

    return refresh_token_state(refresh_token), 200


@api_bp.route("/register", methods=[POST])
def register():
    data = UserRegister(**request.json)
    user = User.query.filter_by(email=data.email).first()
    if user:
        raise BadRequestException("Email has already registered")

    # hashing password
    user_data = data.dict(exclude={"confirm_password"})
    user_data["password"] = get_password_hash(user_data["password"])

    # save user to db
    user = User(**user_data)
    user.is_active = True

    db.session.add(user)
    db.session.commit()

    return {"msg": "Successfully registered"}


@api_bp.route("/dashboard", methods=[GET])
@auth_required
def dashboard_view(user):
    owned_tasks = Task.query.join(TaskList).filter(TaskList.user_id == user.id)
    pending_tasks = owned_tasks.filter(Task.is_completed.is_(False))
    stats = {
        "total_tasks": owned_tasks.count(),
        "completed_tasks": owned_tasks.filter(Task.is_completed.is_(True)).count(),
        "pending_tasks": pending_tasks.count(),
        "overdue_tasks": pending_tasks.filter(Task.due_date < datetime.utcnow()).count(),
        "high_priority_tasks": pending_tasks.filter(Task.priority == "high").count(),
        "tasklists": TaskList.query.filter_by(user_id=user.id).count(),
    }

    if user.role == "admin":
        stats["active_users"] = User.query.filter_by(is_active=True).count()

    return DashboardStatsScheme(**stats).dict() | {
        key: value for key, value in stats.items() if key not in DashboardStatsScheme.__fields__
    }, 200


@api_bp.route("/tasks", methods=[GET])
@auth_required
def tasks_search_view(user):
    query = Task.query.join(TaskList).filter(TaskList.user_id == user.id)
    tasks = _filtered_tasks_query(query)
    return [TaskScheme.from_orm(task).dict() for task in tasks], 200


# ----------------- TaskList list, create, update order view -------------
@api_bp.route("/tasklist", methods=[GET, POST, PATCH])
@auth_required
def tasklists_view(user):
    if request.method == POST:
        tasklist_data = TaskListCreateScheme(**request.json)
        tasklist = TaskList(**tasklist_data.dict())
        tasklist.user_id = user.id

        tasklist.order = 1
        last_task = (
            TaskList.query.filter_by(user_id=user.id)
            .order_by(TaskList.order.desc(), TaskList.created_at.desc())
            .first()
        )
        if last_task:
            tasklist.order += last_task.order

        db.session.add(tasklist)
        db.session.commit()

        return TaskListScheme.from_orm(tasklist).dict(), 201

    elif request.method == PATCH:
        order_data = UpdateOrderScheme(**request.json)

        query = TaskList.query.filter_by(user_id=user.id)

        tasklists = query.order_by(TaskList.order.desc(), TaskList.created_at.desc())
        tasklist = query.filter_by(id=order_data.id).first()

        if not tasklist:
            raise ValidationError(
                errors=[ErrorWrapper(ValueError("Tasklist is not found"), loc="id")]
            )

        last_order = tasklists.first()
        if last_order.order < order_data.order:
            raise ValidationError(
                errors=[
                    ErrorWrapper(
                        ValueError("Value is bigger than tasklists count"), loc="order"
                    )
                ]
            )
        updated_tasklists = []
        for tl in tasklists:
            if tl.id == tasklist.id:
                continue
            c = False
            if order_data.order <= tl.order and tasklist.order > tl.order:
                c = True
                tl.order += 1
            elif order_data.order >= tl.order and tasklist.order < tl.order:
                c = True
                tl.order -= 1
            if c:
                updated_tasklists.append(tl)

        tasklist.order = order_data.order
        updated_tasklists.append(tasklist)
        db.session.bulk_save_objects(updated_tasklists)
        db.session.commit()

    tasklists = TaskList.query.filter_by(user_id=user.id).order_by(
        TaskList.order.asc(), TaskList.created_at.asc()
    )

    return [TaskListScheme.from_orm(tasklist).dict() for tasklist in tasklists], 200


# -------- Tasklist Detail and update view --------
@api_bp.route("/tasklist/<uuid:tasklist_id>", methods=[GET, PUT, DELETE])
@auth_required
def tasklist_view(user, tasklist_id):
    tasklist: TaskList = TaskList.query.filter_by(
        user_id=user.id, id=tasklist_id
    ).first()
    if not tasklist:
        raise NotFoundException(message="Tasklist Not Found")

    if request.method == PUT:
        return _tasklist_view_put(tasklist)
    elif request.method == DELETE:
        db.session.delete(tasklist)
        db.session.commit()
        return None, 200

    return TaskListScheme.from_orm(tasklist).dict(), 200


def _tasklist_view_put(tasklist: TaskList):
    """Update tasklist"""
    tasklist_data = TaskListCreateScheme(**request.json)

    tasklist.title = tasklist_data.title
    tasklist.description = tasklist_data.description
    db.session.commit()

    return TaskListScheme.from_orm(tasklist).dict(), 200


# Tasks list, create, update order view
@api_bp.route("/tasklist/<uuid:tasklist_id>/tasks", methods=[GET, POST, PATCH])
@auth_required
def tasks_view(user, tasklist_id):
    tasklist: TaskList = TaskList.query.filter_by(
        user_id=user.id, id=tasklist_id
    ).first()
    if not tasklist:
        raise NotFoundException(message="Tasklist Not Found")

    if request.method == POST:
        return _tasks_view_post(tasklist)

    elif request.method == PATCH:
        return _tasks_view_patch(tasklist)

    tasks = _filtered_tasks_query(Task.query.filter_by(tasklist_id=tasklist_id))
    return [TaskScheme.from_orm(task).dict() for task in tasks], 200


def _tasks_view_post(tasklist: TaskList):
    """Create new task"""
    task_data = TaskCreateScheme(**request.json)
    task_data_dict = task_data.dict()

    steps_data = task_data_dict.pop("steps")

    task = Task(**task_data_dict)
    task.tasklist_id = tasklist.id
    task.order = 1

    last_task = (
        Task.query.filter_by(tasklist_id=tasklist.id, is_completed=False)
        .order_by(Task.order.desc(), Task.created_at.desc())
        .first()
    )

    if last_task:
        task.order += last_task.order

    db.session.add(task)
    db.session.commit()
    if steps_data:
        steps = [Step(**data) for data in steps_data]
        for step in steps:
            step.task_id = task.id

        db.session.add_all(steps)
        db.session.commit()

    return TaskScheme.from_orm(task).dict(), 201


def _tasks_view_patch(tasklist: TaskList):
    """Update task order"""
    task_data = UpdateOrderScheme(**request.json)
    task: Task = Task.query.filter_by(tasklist_id=tasklist.id, id=task_data.id).first()
    if not task:
        raise ValidationError(
            errors=[ErrorWrapper(ValueError("Task is not found"), loc="id")]
        )

    tasks = (
        Task.query.filter(Task.id != task_data.id)
        .filter_by(tasklist_id=tasklist.id)
        .order_by(Task.order.desc(), Task.created_at.desc())
    )
    last_task: Task = tasks.first()

    if last_task.order < task_data.order:
        raise ValidationError(
            errors=[
                ErrorWrapper(
                    ValueError("Value is bigger than tasks count"), loc="order"
                )
            ]
        )

    updated_tasks = []
    for t in tasks:
        c = False
        if task_data.order <= t.order and task.order > t.order:
            c = True
            t.order += 1
        elif task_data.order >= t.order and task.order < t.order:
            c = True
            t.order -= 1
        if c:
            updated_tasks.append(t)

    task.order = task_data.order
    updated_tasks.append(task)
    db.session.bulk_save_objects(updated_tasks)
    db.session.commit()

    return [
        TaskScheme.from_orm(task).dict()
        for task in Task.query.options(joinedload(Task.steps))
        .filter_by(tasklist_id=tasklist.id)
        .order_by()
    ], 200


@api_bp.route(
    "/tasklist/<uuid:tasklist_id>/tasks/<uuid:task_id>",
    methods=[GET, PATCH, DELETE],
)
@auth_required
def task_view(user, tasklist_id, task_id):
    tasklist: TaskList = TaskList.query.filter_by(
        user_id=user.id, id=tasklist_id
    ).first()

    if not tasklist:
        raise NotFoundException("Tasklist not found")

    task: Task = (
        Task.query.options(joinedload(Task.steps))
        .filter_by(tasklist_id=tasklist.id, id=task_id)
        .first()
    )

    if not task:
        raise NotFoundException("Task not found")

    if request.method == PATCH:
        task_data = TaskPartialUpdateSchema(**request.json).dict(exclude_unset=True)
        for key in Task.__table__.columns.keys():
            if key in task_data:
                setattr(task, key, task_data[key])
        db.session.commit()

    elif request.method == DELETE:
        db.session.delete(task)
        db.session.commit()
        return None, 200

    return TaskScheme.from_orm(task).dict(), 200


@api_bp.route("/tasklist/<uuid:tasklist_id>/tasks/<uuid:task_id>/steps", methods=[POST])
@auth_required
def steps_view(user, tasklist_id, task_id):
    tasklist: TaskList = TaskList.query.filter_by(
        user_id=user.id, id=tasklist_id
    ).first()

    if not tasklist:
        raise NotFoundException("Tasklist not found")

    task: Task = Task.query.filter_by(tasklist_id=tasklist.id, id=task_id).first()

    if not task:
        raise NotFoundException("Task not found")

    step_data = StepCreateScheme(**request.json)
    step = Step(**step_data.dict())
    step.task_id = task.id
    db.session.add(step)
    db.session.commit()
    return StepScheme.from_orm(step).dict(), 201


@api_bp.route(
    "/tasklist/<uuid:tasklist_id>/tasks/<uuid:task_id>/steps/<uuid:step_id>",
    methods=[PUT, DELETE],
)
@auth_required
def step_view(user, tasklist_id, task_id, step_id):
    tasklist: TaskList = TaskList.query.filter_by(
        user_id=user.id, id=tasklist_id
    ).first()

    if not tasklist:
        raise NotFoundException("Tasklist not found")

    task: Task = Task.query.filter_by(tasklist_id=tasklist.id, id=task_id).first()

    if not task:
        raise NotFoundException("Task not found")

    step = Step.query.filter_by(id=step_id, task_id=task_id).first()
    if not step:
        raise NotFoundException("Step not found")

    if request.method == DELETE:
        db.session.delete(step)
        db.session.commit()
        return None, 200

    step_data = StepCreateScheme(**request.json)
    step.title = step_data.title
    db.session.commit()

    return StepScheme.from_orm(step).dict(), 200
