import pathlib

import httpx
from aiogram.types import Update
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database as db
from bot_core import bot, dp
from config import ADMIN_IDS, BOT_TOKEN, DEV_MODE, WEBHOOK_SECRET, WEBHOOK_URL
from webapp.auth import validate_init_data

BASE_DIR = pathlib.Path(__file__).parent

app = FastAPI(title="HR Boshqaruv Mini App")


@app.on_event("startup")
async def on_startup() -> None:
    await db.init_db()
    if WEBHOOK_URL:
        await bot.set_webhook(
            url=f"{WEBHOOK_URL.rstrip('/')}/webhook/{WEBHOOK_SECRET}",
            secret_token=WEBHOOK_SECRET,
            drop_pending_updates=True,
        )
    else:
        await bot.delete_webhook(drop_pending_updates=True)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await bot.session.close()


@app.post("/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Noto'g'ri webhook secret")
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


async def send_telegram_message(chat_id: int, text: str) -> bool:
    if not BOT_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={"chat_id": chat_id, "text": text})
            return resp.status_code == 200
    except Exception:
        return False


async def get_telegram_id(
    x_init_data: str | None = Header(default=None, alias="X-Init-Data"),
    x_dev_tg_id: str | None = Header(default=None, alias="X-Dev-Tg-Id"),
) -> int:
    if x_init_data:
        user = validate_init_data(x_init_data, BOT_TOKEN)
        if not user:
            raise HTTPException(status_code=401, detail="Init data noto'g'ri")
        return int(user["id"])
    if DEV_MODE and x_dev_tg_id:
        return int(x_dev_tg_id)
    raise HTTPException(status_code=401, detail="Avtorizatsiya talab qilinadi")


async def require_admin(tg_id: int = Depends(get_telegram_id)) -> int:
    if tg_id not in ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")
    return tg_id


async def require_employee(tg_id: int = Depends(get_telegram_id)) -> dict:
    employee = await db.get_employee_by_telegram_id(tg_id)
    if not employee or employee["status"] != "approved":
        raise HTTPException(status_code=403, detail="Tasdiqlangan xodim emassiz")
    return employee


# ---------- Profile / registration ----------

@app.get("/api/profile")
async def profile(tg_id: int = Depends(get_telegram_id)):
    if tg_id in ADMIN_IDS:
        return {"role": "admin"}
    employee = await db.get_employee_by_telegram_id(tg_id)
    if not employee:
        return {"role": "unregistered"}
    if employee["status"] == "pending":
        return {"role": "pending"}
    if employee["status"] == "rejected":
        return {"role": "rejected"}
    return {"role": "employee", "employee": employee}


class RegisterBody(BaseModel):
    full_name: str
    phone: str


@app.post("/api/register")
async def register(body: RegisterBody, tg_id: int = Depends(get_telegram_id)):
    existing = await db.get_employee_by_telegram_id(tg_id)
    if existing:
        await db.resubmit_registration(existing["id"], body.full_name, body.phone)
    else:
        await db.add_pending_employee(tg_id, body.full_name, body.phone)

    for admin_id in ADMIN_IDS:
        await send_telegram_message(
            admin_id,
            f"🆕 Yangi xodim so'rovi (Mini App):\n👤 {body.full_name}\n📱 {body.phone}\n\n"
            f"Ko'rib chiqish uchun Mini App dagi \"Yangi so'rovlar\" bo'limini oching.",
        )
    return {"ok": True}


# ---------- Employee endpoints ----------

@app.post("/api/attendance/checkin")
async def api_checkin(employee: dict = Depends(require_employee)):
    ok = await db.check_in(employee["id"])
    return {"ok": ok}


@app.post("/api/attendance/checkout")
async def api_checkout(employee: dict = Depends(require_employee)):
    ok = await db.check_out(employee["id"])
    return {"ok": ok}


@app.post("/api/attendance/lunch-out")
async def api_lunch_out(employee: dict = Depends(require_employee)):
    ok = await db.lunch_out(employee["id"])
    return {"ok": ok}


@app.post("/api/attendance/lunch-in")
async def api_lunch_in(employee: dict = Depends(require_employee)):
    ok = await db.lunch_in(employee["id"])
    return {"ok": ok}


@app.get("/api/attendance/today")
async def api_today(employee: dict = Depends(require_employee)):
    return await db.get_today_attendance(employee["id"]) or {}


class LeaveBody(BaseModel):
    leave_type: str
    start_date: str
    end_date: str
    reason: str


@app.post("/api/leave")
async def api_leave(body: LeaveBody, employee: dict = Depends(require_employee)):
    leave_id = await db.add_leave_request(
        employee["id"], body.leave_type, body.start_date, body.end_date, body.reason
    )
    for admin_id in ADMIN_IDS:
        await send_telegram_message(
            admin_id,
            f"🌴 Yangi ta'til so'rovi (Mini App):\n👤 {employee['full_name']}\n"
            f"📌 {body.leave_type}: {body.start_date} — {body.end_date}\n📝 {body.reason}\n\n"
            f"Ko'rib chiqish uchun Mini App dagi \"Ta'til so'rovlari\" bo'limini oching.",
        )
    return {"ok": True, "id": leave_id}


@app.get("/api/leave/history")
async def api_leave_history(employee: dict = Depends(require_employee)):
    return await db.list_leave_requests_by_employee(employee["id"])


@app.get("/api/tasks")
async def api_tasks(employee: dict = Depends(require_employee)):
    return await db.list_tasks_by_employee(employee["id"])


@app.post("/api/tasks/{task_id}/done")
async def api_task_done(task_id: int, employee: dict = Depends(require_employee)):
    task = await db.get_task(task_id)
    if not task or task["employee_id"] != employee["id"]:
        raise HTTPException(status_code=404, detail="Topilmadi")
    await db.update_task_status(task_id, "done")
    for admin_id in ADMIN_IDS:
        await send_telegram_message(
            admin_id, f"✅ {employee['full_name']} \"{task['title']}\" vazifasini bajardi."
        )
    return {"ok": True}


@app.get("/api/salary")
async def api_salary(employee: dict = Depends(require_employee)):
    return {"salary": employee["salary"]}


# ---------- Admin endpoints ----------

@app.get("/api/admin/employees")
async def admin_employees(_: int = Depends(require_admin)):
    return await db.list_employees("approved")


class AddEmployeeBody(BaseModel):
    telegram_id: int
    full_name: str
    phone: str
    position: str
    department: str
    salary: float = 0


@app.post("/api/admin/employees")
async def admin_add_employee(body: AddEmployeeBody, _: int = Depends(require_admin)):
    employee_id = await db.add_employee_direct(
        body.telegram_id, body.full_name, body.phone, body.position, body.department, body.salary
    )
    sent = await send_telegram_message(
        body.telegram_id,
        f"🎉 Siz HR tizimiga xodim sifatida qo'shildingiz!\n"
        f"💼 Lavozim: {body.position}\n🏢 Bo'lim: {body.department}\n\n"
        f"Botga /start yozib to'liq imkoniyatlardan foydalaning.",
    )
    return {"ok": True, "id": employee_id, "notified": sent}


@app.get("/api/admin/activity")
async def admin_activity(_: int = Depends(require_admin)):
    return await db.get_recent_activity(30)


@app.get("/api/admin/pending")
async def admin_pending(_: int = Depends(require_admin)):
    return await db.list_pending_employees()


class ApproveBody(BaseModel):
    position: str
    department: str
    salary: float


@app.post("/api/admin/employees/{employee_id}/approve")
async def admin_approve(employee_id: int, body: ApproveBody, _: int = Depends(require_admin)):
    await db.approve_employee(employee_id, body.position, body.department, body.salary)
    employee = await db.get_employee_by_id(employee_id)
    await send_telegram_message(
        employee["telegram_id"],
        f"🎉 Tabriklaymiz! So'rovingiz tasdiqlandi.\n💼 {body.position}\n🏢 {body.department}",
    )
    return {"ok": True}


@app.post("/api/admin/employees/{employee_id}/reject")
async def admin_reject(employee_id: int, _: int = Depends(require_admin)):
    employee = await db.get_employee_by_id(employee_id)
    await db.reject_employee(employee_id)
    await send_telegram_message(employee["telegram_id"], "❌ Afsuski, so'rovingiz rad etildi.")
    return {"ok": True}


@app.delete("/api/admin/employees/{employee_id}")
async def admin_delete(employee_id: int, _: int = Depends(require_admin)):
    await db.delete_employee(employee_id)
    return {"ok": True}


@app.get("/api/admin/leaves")
async def admin_leaves(_: int = Depends(require_admin)):
    return await db.list_all_leave_requests()


@app.post("/api/admin/leaves/{leave_id}/approve")
async def admin_leave_approve(leave_id: int, _: int = Depends(require_admin)):
    leave = await db.get_leave_request(leave_id)
    await db.update_leave_status(leave_id, "approved")
    await send_telegram_message(leave["telegram_id"], "✅ Sizning ta'til so'rovingiz tasdiqlandi.")
    return {"ok": True}


@app.post("/api/admin/leaves/{leave_id}/reject")
async def admin_leave_reject(leave_id: int, _: int = Depends(require_admin)):
    leave = await db.get_leave_request(leave_id)
    await db.update_leave_status(leave_id, "rejected")
    await send_telegram_message(leave["telegram_id"], "❌ Sizning ta'til so'rovingiz rad etildi.")
    return {"ok": True}


class TaskBody(BaseModel):
    employee_id: int
    title: str
    description: str
    deadline: str


@app.post("/api/admin/tasks")
async def admin_add_task(body: TaskBody, _: int = Depends(require_admin)):
    await db.add_task(body.employee_id, body.title, body.description, body.deadline)
    employee = await db.get_employee_by_id(body.employee_id)
    await send_telegram_message(
        employee["telegram_id"],
        f"📋 Sizga yangi vazifa berildi:\n{body.title}\n{body.description}\n⏰ Muddat: {body.deadline}",
    )
    return {"ok": True}


@app.get("/api/admin/tasks")
async def admin_tasks(_: int = Depends(require_admin)):
    return await db.list_all_tasks()


class SalaryBody(BaseModel):
    employee_id: int
    amount: float


@app.post("/api/admin/salary")
async def admin_salary(body: SalaryBody, _: int = Depends(require_admin)):
    await db.set_salary(body.employee_id, body.amount)
    employee = await db.get_employee_by_id(body.employee_id)
    await send_telegram_message(
        employee["telegram_id"],
        f"💰 Sizning oylik maoshingiz yangilandi: {body.amount:,.0f} so'm".replace(",", " "),
    )
    return {"ok": True}


class AnnouncementBody(BaseModel):
    text: str


@app.post("/api/admin/announcement")
async def admin_announcement(body: AnnouncementBody, _: int = Depends(require_admin)):
    await db.add_announcement(body.text)
    employees = await db.list_employees("approved")
    sent = 0
    for emp in employees:
        ok = await send_telegram_message(emp["telegram_id"], f"📢 E'lon\n\n{body.text}")
        if ok:
            sent += 1
    return {"ok": True, "sent": sent, "total": len(employees)}


@app.get("/api/admin/stats")
async def admin_stats(_: int = Depends(require_admin)):
    return await db.get_stats()


app.mount("/", StaticFiles(directory=BASE_DIR / "static", html=True), name="static")
