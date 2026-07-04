from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import database as db
import keyboards as kb
from config import ADMIN_IDS
from states import Broadcast, SalaryEdit, TaskAssign

router = Router()
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))


# ---------- Employees list ----------

@router.message(StateFilter(None), F.text == "👥 Xodimlar")
async def list_employees(message: Message) -> None:
    employees = await db.list_employees("approved")
    if not employees:
        await message.answer("📭 Hozircha tasdiqlangan xodim yo'q.")
        return
    for emp in employees:
        text = (
            f"👤 <b>{emp['full_name']}</b>\n"
            f"💼 {emp['position'] or '-'} | 🏢 {emp['department'] or '-'}\n"
            f"📱 {emp['phone'] or '-'} | 💰 {emp['salary']:,.0f} so'm".replace(",", " ")
        )
        await message.answer(text, parse_mode="HTML", reply_markup=kb.employee_manage_kb(emp["id"]))


@router.callback_query(F.data.startswith("emp_delete:"))
async def delete_employee_cb(callback: CallbackQuery) -> None:
    employee_id = int(callback.data.split(":")[1])
    employee = await db.get_employee_by_id(employee_id)
    await db.delete_employee(employee_id)
    await callback.message.edit_text(f"🗑 {employee['full_name']} tizimdan o'chirildi.")
    await callback.answer()


@router.message(StateFilter(None), F.text == "🆕 Yangi so'rovlar")
async def list_pending(message: Message) -> None:
    pending = await db.list_pending_employees()
    if not pending:
        await message.answer("📭 Yangi so'rovlar yo'q.")
        return
    for emp in pending:
        await message.answer(
            f"👤 {emp['full_name']}\n📱 {emp['phone']}",
            reply_markup=kb.approve_reject_kb(emp["id"]),
        )


# ---------- Leave requests ----------

@router.message(StateFilter(None), F.text == "🌴 Ta'til so'rovlari")
async def list_leave_requests(message: Message) -> None:
    requests = await db.list_pending_leave_requests()
    if not requests:
        await message.answer("📭 Ko'rib chiqilmagan so'rovlar yo'q.")
        return
    for r in requests:
        text = (
            f"👤 {r['full_name']}\n"
            f"📌 {r['leave_type']}: {r['start_date']} — {r['end_date']}\n"
            f"📝 {r['reason'] or '-'}"
        )
        await message.answer(text, reply_markup=kb.leave_decision_kb(r["id"]))


@router.callback_query(F.data.startswith("leave_approve:"))
async def leave_approve_cb(callback: CallbackQuery, bot: Bot) -> None:
    leave_id = int(callback.data.split(":")[1])
    leave = await db.get_leave_request(leave_id)
    await db.update_leave_status(leave_id, "approved")
    await callback.message.edit_text(f"✅ {leave['full_name']} ning so'rovi tasdiqlandi.")
    await callback.answer()
    try:
        await bot.send_message(leave["telegram_id"], "✅ Sizning ta'til so'rovingiz tasdiqlandi.")
    except Exception:
        pass


@router.callback_query(F.data.startswith("leave_reject:"))
async def leave_reject_cb(callback: CallbackQuery, bot: Bot) -> None:
    leave_id = int(callback.data.split(":")[1])
    leave = await db.get_leave_request(leave_id)
    await db.update_leave_status(leave_id, "rejected")
    await callback.message.edit_text(f"❌ {leave['full_name']} ning so'rovi rad etildi.")
    await callback.answer()
    try:
        await bot.send_message(leave["telegram_id"], "❌ Sizning ta'til so'rovingiz rad etildi.")
    except Exception:
        pass


# ---------- Broadcast ----------

@router.message(StateFilter(None), F.text == "📢 E'lon yuborish")
async def broadcast_start(message: Message, state: FSMContext) -> None:
    await state.set_state(Broadcast.waiting_text)
    await message.answer("📢 E'lon matnini kiriting:")


@router.message(Broadcast.waiting_text, F.text)
async def broadcast_send(message: Message, state: FSMContext, bot: Bot) -> None:
    text = message.text.strip()
    await state.clear()
    await db.add_announcement(text)

    employees = await db.list_employees("approved")
    sent = 0
    for emp in employees:
        try:
            await bot.send_message(emp["telegram_id"], f"📢 <b>E'lon</b>\n\n{text}", parse_mode="HTML")
            sent += 1
        except Exception:
            pass
    await message.answer(f"✅ E'lon {sent}/{len(employees)} xodimga yuborildi.")


# ---------- Task assignment ----------

@router.message(StateFilter(None), F.text == "✅ Vazifa berish")
async def task_assign_start(message: Message) -> None:
    employees = await db.list_employees("approved")
    if not employees:
        await message.answer("📭 Tasdiqlangan xodim yo'q.")
        return
    await message.answer("Xodimni tanlang:", reply_markup=kb.employee_picker_kb(employees, "task_pick"))


@router.callback_query(F.data.startswith("task_pick:"))
async def task_assign_pick(callback: CallbackQuery, state: FSMContext) -> None:
    employee_id = int(callback.data.split(":")[1])
    await state.update_data(employee_id=employee_id)
    await state.set_state(TaskAssign.waiting_title)
    await callback.message.edit_text("📝 Vazifa nomini kiriting:")
    await callback.answer()


@router.message(TaskAssign.waiting_title, F.text)
async def task_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(TaskAssign.waiting_description)
    await message.answer("📄 Vazifa tavsifini kiriting:")


@router.message(TaskAssign.waiting_description, F.text)
async def task_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await state.set_state(TaskAssign.waiting_deadline)
    await message.answer("⏰ Muddatini kiriting (YYYY-MM-DD):")


@router.message(TaskAssign.waiting_deadline, F.text)
async def task_deadline(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    employee_id = data["employee_id"]
    deadline = message.text.strip()
    await db.add_task(employee_id, data["title"], data["description"], deadline)
    await state.clear()

    employee = await db.get_employee_by_id(employee_id)
    await message.answer(f"✅ Vazifa {employee['full_name']} ga biriktirildi.")

    try:
        await bot.send_message(
            employee["telegram_id"],
            f"📋 Sizga yangi vazifa berildi:\n\n"
            f"<b>{data['title']}</b>\n{data['description']}\n⏰ Muddat: {deadline}",
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(StateFilter(None), F.text == "📋 Vazifalar holati")
async def all_tasks(message: Message) -> None:
    tasks = await db.list_all_tasks()
    if not tasks:
        await message.answer("📭 Hozircha vazifalar yo'q.")
        return
    lines = []
    for t in tasks:
        icon = "✅" if t["status"] == "done" else "🕒"
        lines.append(f"{icon} {t['full_name']}: {t['title']} (muddat: {t['deadline'] or '-'})")
    await message.answer("\n".join(lines))


# ---------- Salary ----------

@router.message(StateFilter(None), F.text == "💰 Maosh belgilash")
async def salary_start(message: Message) -> None:
    employees = await db.list_employees("approved")
    if not employees:
        await message.answer("📭 Tasdiqlangan xodim yo'q.")
        return
    await message.answer("Xodimni tanlang:", reply_markup=kb.employee_picker_kb(employees, "salary_pick"))


@router.callback_query(F.data.startswith("salary_pick:"))
async def salary_pick(callback: CallbackQuery, state: FSMContext) -> None:
    employee_id = int(callback.data.split(":")[1])
    await state.update_data(employee_id=employee_id)
    await state.set_state(SalaryEdit.waiting_amount)
    await callback.message.edit_text("💰 Yangi oylik maoshni kiriting (faqat son):")
    await callback.answer()


@router.message(SalaryEdit.waiting_amount, F.text)
async def salary_amount(message: Message, state: FSMContext, bot: Bot) -> None:
    try:
        salary = float(message.text.strip().replace(" ", "").replace(",", "."))
    except ValueError:
        await message.answer("❗ Iltimos, faqat son kiriting. Masalan: 4500000")
        return

    data = await state.get_data()
    employee_id = data["employee_id"]
    await db.set_salary(employee_id, salary)
    await state.clear()

    employee = await db.get_employee_by_id(employee_id)
    await message.answer(f"✅ {employee['full_name']} ning maoshi {salary:,.0f} so'm etib belgilandi.".replace(",", " "))

    try:
        await bot.send_message(
            employee["telegram_id"],
            f"💰 Sizning oylik maoshingiz yangilandi: {salary:,.0f} so'm".replace(",", " "),
        )
    except Exception:
        pass


# ---------- Stats ----------

@router.message(StateFilter(None), F.text == "📊 Hisobot")
async def stats(message: Message) -> None:
    s = await db.get_stats()
    await message.answer(
        "📊 <b>Umumiy hisobot</b>\n\n"
        f"👥 Jami xodimlar: {s['total_employees']}\n"
        f"✅ Bugun kelganlar: {s['present_today']}\n"
        f"🆕 Kutilayotgan so'rovlar: {s['pending_registrations']}\n"
        f"🌴 Kutilayotgan ta'til so'rovlari: {s['pending_leaves']}\n"
        f"📋 Vazifalar: {s['tasks_done']}/{s['tasks_total']} bajarilgan",
        parse_mode="HTML",
    )
