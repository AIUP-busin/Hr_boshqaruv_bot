import datetime
import re

import asyncpg

from config import DATABASE_URL

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    phone TEXT,
    position TEXT,
    department TEXT,
    salary REAL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending', -- pending | approved | rejected
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attendance (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    check_in TEXT,
    lunch_out TEXT,
    lunch_in TEXT,
    check_out TEXT,
    UNIQUE(employee_id, date)
);

ALTER TABLE attendance ADD COLUMN IF NOT EXISTS lunch_out TEXT;
ALTER TABLE attendance ADD COLUMN IF NOT EXISTS lunch_in TEXT;

CREATE TABLE IF NOT EXISTS leave_requests (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    leave_type TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending', -- pending | approved | rejected
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    deadline TEXT,
    status TEXT NOT NULL DEFAULT 'new', -- new | done
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS announcements (
    id SERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_log (
    id SERIAL PRIMARY KEY,
    icon TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

_pool: asyncpg.Pool | None = None


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return datetime.date.today().isoformat()


def _to_dollar_params(query: str) -> str:
    """SQLite-uslubidagi '?' o'rniga Postgres '$1, $2, ...' placeholderlarga o'giradi."""
    counter = 0

    def repl(_match: re.Match) -> str:
        nonlocal counter
        counter += 1
        return f"${counter}"

    return re.sub(r"\?", repl, query)


async def init_db() -> None:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with _pool.acquire() as conn:
        await conn.execute(SCHEMA)


async def _fetch_one(query: str, params: tuple = ()) -> dict | None:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(_to_dollar_params(query), *params)
        return dict(row) if row is not None else None


async def _fetch_all(query: str, params: tuple = ()) -> list[dict]:
    async with _pool.acquire() as conn:
        rows = await conn.fetch(_to_dollar_params(query), *params)
        return [dict(r) for r in rows]


async def _execute(query: str, params: tuple = ()) -> None:
    async with _pool.acquire() as conn:
        await conn.execute(_to_dollar_params(query), *params)


async def _insert(query: str, params: tuple = ()) -> int:
    """INSERT ... so'rovini bajaradi va yangi qatorning id'sini qaytaradi.

    `query` oxirida `RETURNING id` bo'lishi shart.
    """
    async with _pool.acquire() as conn:
        return await conn.fetchval(_to_dollar_params(query), *params)


# ---------- Activity log ----------

async def log_activity(icon: str, text: str) -> None:
    await _execute(
        "INSERT INTO activity_log (icon, text, created_at) VALUES (?, ?, ?)",
        (icon, text, _now()),
    )


async def get_recent_activity(limit: int = 20) -> list[dict]:
    return await _fetch_all(
        "SELECT * FROM activity_log ORDER BY id DESC LIMIT ?", (limit,)
    )


# ---------- Employees ----------

async def add_pending_employee(telegram_id: int, full_name: str, phone: str) -> int:
    employee_id = await _insert(
        "INSERT INTO employees (telegram_id, full_name, phone, status, created_at) "
        "VALUES (?, ?, ?, 'pending', ?) RETURNING id",
        (telegram_id, full_name, phone, _now()),
    )
    await log_activity("🆕", f"{full_name} ro'yxatdan o'tish uchun so'rov yubordi")
    return employee_id


async def add_employee_direct(
    telegram_id: int, full_name: str, phone: str, position: str, department: str, salary: float
) -> int:
    existing = await get_employee_by_telegram_id(telegram_id)
    if existing:
        await _execute(
            "UPDATE employees SET full_name = ?, phone = ?, position = ?, department = ?, "
            "salary = ?, status = 'approved' WHERE id = ?",
            (full_name, phone, position, department, salary, existing["id"]),
        )
        employee_id = existing["id"]
    else:
        employee_id = await _insert(
            "INSERT INTO employees (telegram_id, full_name, phone, position, department, salary, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'approved', ?) RETURNING id",
            (telegram_id, full_name, phone, position, department, salary, _now()),
        )
    await log_activity("➕", f"{full_name} admin tomonidan xodim sifatida qo'shildi")
    return employee_id


async def get_employee_by_telegram_id(telegram_id: int) -> dict | None:
    return await _fetch_one("SELECT * FROM employees WHERE telegram_id = ?", (telegram_id,))


async def get_employee_by_id(employee_id: int) -> dict | None:
    return await _fetch_one("SELECT * FROM employees WHERE id = ?", (employee_id,))


async def resubmit_registration(employee_id: int, full_name: str, phone: str) -> None:
    await _execute(
        "UPDATE employees SET full_name = ?, phone = ?, status = 'pending' WHERE id = ?",
        (full_name, phone, employee_id),
    )


async def approve_employee(employee_id: int, position: str, department: str, salary: float) -> None:
    await _execute(
        "UPDATE employees SET status = 'approved', position = ?, department = ?, salary = ? WHERE id = ?",
        (position, department, salary, employee_id),
    )
    employee = await get_employee_by_id(employee_id)
    if employee:
        await log_activity("✅", f"{employee['full_name']} xodim sifatida tasdiqlandi")


async def reject_employee(employee_id: int) -> None:
    employee = await get_employee_by_id(employee_id)
    await _execute("UPDATE employees SET status = 'rejected' WHERE id = ?", (employee_id,))
    if employee:
        await log_activity("❌", f"{employee['full_name']} so'rovi rad etildi")


async def delete_employee(employee_id: int) -> None:
    employee = await get_employee_by_id(employee_id)
    await _execute("DELETE FROM employees WHERE id = ?", (employee_id,))
    if employee:
        await log_activity("🗑", f"{employee['full_name']} tizimdan o'chirildi")


async def set_salary(employee_id: int, salary: float) -> None:
    await _execute("UPDATE employees SET salary = ? WHERE id = ?", (salary, employee_id))
    employee = await get_employee_by_id(employee_id)
    if employee:
        await log_activity("💰", f"{employee['full_name']} maoshi {salary:,.0f} so'mga yangilandi".replace(",", " "))


async def list_employees(status: str = "approved") -> list[dict]:
    return await _fetch_all(
        "SELECT * FROM employees WHERE status = ? ORDER BY full_name", (status,)
    )


async def list_pending_employees() -> list[dict]:
    return await list_employees("pending")


# ---------- Attendance ----------

async def check_in(employee_id: int) -> bool:
    existing = await _fetch_one(
        "SELECT * FROM attendance WHERE employee_id = ? AND date = ?",
        (employee_id, _today()),
    )
    if existing and existing["check_in"]:
        return False
    if existing:
        await _execute(
            "UPDATE attendance SET check_in = ? WHERE id = ?",
            (_now(), existing["id"]),
        )
    else:
        await _execute(
            "INSERT INTO attendance (employee_id, date, check_in) VALUES (?, ?, ?)",
            (employee_id, _today(), _now()),
        )
    employee = await get_employee_by_id(employee_id)
    if employee:
        await log_activity("🟢", f"{employee['full_name']} ishga keldi")
    return True


async def check_out(employee_id: int) -> bool:
    existing = await _fetch_one(
        "SELECT * FROM attendance WHERE employee_id = ? AND date = ?",
        (employee_id, _today()),
    )
    if not existing or not existing["check_in"]:
        return False
    if existing["check_out"]:
        return False
    await _execute(
        "UPDATE attendance SET check_out = ? WHERE id = ?",
        (_now(), existing["id"]),
    )
    employee = await get_employee_by_id(employee_id)
    if employee:
        await log_activity("🔴", f"{employee['full_name']} ishdan ketdi")
    return True


async def lunch_out(employee_id: int) -> bool:
    existing = await _fetch_one(
        "SELECT * FROM attendance WHERE employee_id = ? AND date = ?",
        (employee_id, _today()),
    )
    if not existing or not existing["check_in"] or existing["check_out"]:
        return False
    if existing["lunch_out"]:
        return False
    await _execute(
        "UPDATE attendance SET lunch_out = ? WHERE id = ?",
        (_now(), existing["id"]),
    )
    employee = await get_employee_by_id(employee_id)
    if employee:
        await log_activity("🍽", f"{employee['full_name']} tushlikka chiqdi")
    return True


async def lunch_in(employee_id: int) -> bool:
    existing = await _fetch_one(
        "SELECT * FROM attendance WHERE employee_id = ? AND date = ?",
        (employee_id, _today()),
    )
    if not existing or not existing["lunch_out"] or existing["check_out"]:
        return False
    if existing["lunch_in"]:
        return False
    await _execute(
        "UPDATE attendance SET lunch_in = ? WHERE id = ?",
        (_now(), existing["id"]),
    )
    employee = await get_employee_by_id(employee_id)
    if employee:
        await log_activity("🍽", f"{employee['full_name']} tushlikdan qaytdi")
    return True


async def get_today_attendance(employee_id: int) -> dict | None:
    return await _fetch_one(
        "SELECT * FROM attendance WHERE employee_id = ? AND date = ?",
        (employee_id, _today()),
    )


async def get_attendance_report(date: str | None = None) -> list[dict]:
    date = date or _today()
    return await _fetch_all(
        """
        SELECT e.full_name, e.department, a.check_in, a.check_out
        FROM employees e
        LEFT JOIN attendance a ON a.employee_id = e.id AND a.date = ?
        WHERE e.status = 'approved'
        ORDER BY e.full_name
        """,
        (date,),
    )


# ---------- Leave requests ----------

async def add_leave_request(employee_id: int, leave_type: str, start_date: str, end_date: str, reason: str) -> int:
    leave_id = await _insert(
        "INSERT INTO leave_requests (employee_id, leave_type, start_date, end_date, reason, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
        (employee_id, leave_type, start_date, end_date, reason, _now()),
    )
    employee = await get_employee_by_id(employee_id)
    if employee:
        await log_activity("🌴", f"{employee['full_name']} {leave_type} so'radi ({start_date} — {end_date})")
    return leave_id


async def list_pending_leave_requests() -> list[dict]:
    return await _fetch_all(
        """
        SELECT lr.*, e.full_name FROM leave_requests lr
        JOIN employees e ON e.id = lr.employee_id
        WHERE lr.status = 'pending'
        ORDER BY lr.created_at
        """
    )


async def list_all_leave_requests() -> list[dict]:
    return await _fetch_all(
        """
        SELECT lr.*, e.full_name FROM leave_requests lr
        JOIN employees e ON e.id = lr.employee_id
        ORDER BY lr.status, lr.created_at DESC
        """
    )


async def get_leave_request(leave_id: int) -> dict | None:
    return await _fetch_one(
        """
        SELECT lr.*, e.full_name, e.telegram_id FROM leave_requests lr
        JOIN employees e ON e.id = lr.employee_id
        WHERE lr.id = ?
        """,
        (leave_id,),
    )


async def update_leave_status(leave_id: int, status: str) -> None:
    await _execute("UPDATE leave_requests SET status = ? WHERE id = ?", (status, leave_id))
    leave = await get_leave_request(leave_id)
    if leave:
        icon = "✅" if status == "approved" else "❌"
        await log_activity(icon, f"{leave['full_name']} ning ta'til so'rovi {status} qilindi")


async def list_leave_requests_by_employee(employee_id: int) -> list[dict]:
    return await _fetch_all(
        "SELECT * FROM leave_requests WHERE employee_id = ? ORDER BY created_at DESC",
        (employee_id,),
    )


# ---------- Announcements ----------

async def add_announcement(text: str) -> int:
    announcement_id = await _insert(
        "INSERT INTO announcements (text, created_at) VALUES (?, ?) RETURNING id", (text, _now())
    )
    preview = text if len(text) <= 60 else text[:57] + "..."
    await log_activity("📢", f"E'lon yuborildi: {preview}")
    return announcement_id


# ---------- Tasks ----------

async def add_task(employee_id: int, title: str, description: str, deadline: str) -> int:
    task_id = await _insert(
        "INSERT INTO tasks (employee_id, title, description, deadline, created_at) "
        "VALUES (?, ?, ?, ?, ?) RETURNING id",
        (employee_id, title, description, deadline, _now()),
    )
    employee = await get_employee_by_id(employee_id)
    if employee:
        await log_activity("📋", f"{employee['full_name']} ga \"{title}\" vazifasi berildi")
    return task_id


async def list_tasks_by_employee(employee_id: int, status: str | None = None) -> list[dict]:
    if status:
        return await _fetch_all(
            "SELECT * FROM tasks WHERE employee_id = ? AND status = ? ORDER BY created_at DESC",
            (employee_id, status),
        )
    return await _fetch_all(
        "SELECT * FROM tasks WHERE employee_id = ? ORDER BY created_at DESC", (employee_id,)
    )


async def get_task(task_id: int) -> dict | None:
    return await _fetch_one(
        """
        SELECT t.*, e.telegram_id, e.full_name FROM tasks t
        JOIN employees e ON e.id = t.employee_id
        WHERE t.id = ?
        """,
        (task_id,),
    )


async def update_task_status(task_id: int, status: str) -> None:
    await _execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
    if status == "done":
        task = await get_task(task_id)
        if task:
            await log_activity("✅", f"{task['full_name']} \"{task['title']}\" vazifasini bajardi")


async def list_all_tasks() -> list[dict]:
    return await _fetch_all(
        """
        SELECT t.*, e.full_name FROM tasks t
        JOIN employees e ON e.id = t.employee_id
        ORDER BY t.status, t.created_at DESC
        """
    )


# ---------- Stats ----------

async def get_stats() -> dict:
    total = await _fetch_one("SELECT COUNT(*) as c FROM employees WHERE status = 'approved'")
    present_today = await _fetch_one(
        "SELECT COUNT(*) as c FROM attendance WHERE date = ? AND check_in IS NOT NULL",
        (_today(),),
    )
    pending_leaves = await _fetch_one(
        "SELECT COUNT(*) as c FROM leave_requests WHERE status = 'pending'"
    )
    pending_registrations = await _fetch_one(
        "SELECT COUNT(*) as c FROM employees WHERE status = 'pending'"
    )
    tasks_total = await _fetch_one("SELECT COUNT(*) as c FROM tasks")
    tasks_done = await _fetch_one("SELECT COUNT(*) as c FROM tasks WHERE status = 'done'")
    return {
        "total_employees": total["c"],
        "present_today": present_today["c"],
        "pending_leaves": pending_leaves["c"],
        "pending_registrations": pending_registrations["c"],
        "tasks_total": tasks_total["c"],
        "tasks_done": tasks_done["c"],
    }
