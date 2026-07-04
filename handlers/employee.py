from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import database as db
import keyboards as kb
from config import ADMIN_IDS
from states import LeaveRequest

router = Router()


async def _get_approved_employee(message: Message) -> dict | None:
    employee = await db.get_employee_by_telegram_id(message.from_user.id)
    if not employee or employee["status"] != "approved":
        await message.answer("❗ Siz hali tizimda ro'yxatdan o'tmagansiz. /start bosing.")
        return None
    return employee


@router.message(StateFilter(None), F.text == "✅ Keldim")
async def check_in(message: Message) -> None:
    employee = await _get_approved_employee(message)
    if not employee:
        return
    ok = await db.check_in(employee["id"])
    if ok:
        await message.answer("✅ Kelganingiz qayd etildi. Xayrli ish kuni!")
    else:
        await message.answer("ℹ️ Siz bugun allaqachon kelganingizni qayd etgansiz.")


@router.message(StateFilter(None), F.text == "🚪 Ketdim")
async def check_out(message: Message) -> None:
    employee = await _get_approved_employee(message)
    if not employee:
        return
    ok = await db.check_out(employee["id"])
    if ok:
        await message.answer("🚪 Ketganingiz qayd etildi. Ko'rishguncha!")
    else:
        today = await db.get_today_attendance(employee["id"])
        if not today or not today["check_in"]:
            await message.answer("❗ Siz bugun hali kelganingizni qayd etmagansiz.")
        else:
            await message.answer("ℹ️ Siz bugun allaqachon ketganingizni qayd etgansiz.")


@router.message(StateFilter(None), F.text == "👤 Profilim")
async def profile(message: Message) -> None:
    employee = await _get_approved_employee(message)
    if not employee:
        return
    await message.answer(
        f"👤 <b>{employee['full_name']}</b>\n"
        f"💼 Lavozim: {employee['position'] or '-'}\n"
        f"🏢 Bo'lim: {employee['department'] or '-'}\n"
        f"📱 Tel: {employee['phone'] or '-'}\n"
        f"📅 Ishga qabul: {employee['created_at'][:10]}",
        parse_mode="HTML",
    )


@router.message(StateFilter(None), F.text == "💰 Mening maoshim")
async def my_salary(message: Message) -> None:
    employee = await _get_approved_employee(message)
    if not employee:
        return
    salary = employee["salary"] or 0
    await message.answer(f"💰 Sizning oylik maoshingiz: <b>{salary:,.0f} so'm</b>".replace(",", " "), parse_mode="HTML")


@router.message(StateFilter(None), F.text == "📋 Mening vazifalarim")
async def my_tasks(message: Message) -> None:
    employee = await _get_approved_employee(message)
    if not employee:
        return
    tasks = await db.list_tasks_by_employee(employee["id"])
    if not tasks:
        await message.answer("📭 Hozircha sizga biriktirilgan vazifa yo'q.")
        return
    for task in tasks:
        status_icon = "✅" if task["status"] == "done" else "🕒"
        text = (
            f"{status_icon} <b>{task['title']}</b>\n"
            f"{task['description'] or ''}\n"
            f"⏰ Muddat: {task['deadline'] or '-'}"
        )
        if task["status"] == "new":
            await message.answer(text, parse_mode="HTML", reply_markup=kb.task_done_kb(task["id"]))
        else:
            await message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("task_done:"))
async def mark_task_done(callback: CallbackQuery, bot: Bot) -> None:
    task_id = int(callback.data.split(":")[1])
    task = await db.get_task(task_id)
    if not task:
        await callback.answer("Topilmadi", show_alert=True)
        return
    await db.update_task_status(task_id, "done")
    await callback.message.edit_text(f"✅ <b>{task['title']}</b>\n\nBajarildi deb belgilandi.", parse_mode="HTML")
    await callback.answer("Rahmat!")

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"✅ {task['full_name']} \"{task['title']}\" vazifasini bajardi.",
            )
        except Exception:
            pass


@router.message(StateFilter(None), F.text == "📜 Ta'til tarixim")
async def leave_history(message: Message) -> None:
    employee = await _get_approved_employee(message)
    if not employee:
        return
    requests = await db.list_leave_requests_by_employee(employee["id"])
    if not requests:
        await message.answer("📭 Sizda hali so'rovlar mavjud emas.")
        return
    icons = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
    lines = []
    for r in requests:
        icon = icons.get(r["status"], "")
        lines.append(f"{icon} {r['leave_type']}: {r['start_date']} — {r['end_date']}")
    await message.answer("\n".join(lines))


# ---------- Leave request flow ----------

@router.message(StateFilter(None), F.text == "🌴 Ta'til so'rash")
async def leave_start(message: Message) -> None:
    employee = await _get_approved_employee(message)
    if not employee:
        return
    await message.answer("Turini tanlang:", reply_markup=kb.leave_type_kb())


@router.callback_query(F.data.startswith("leave_type:"))
async def leave_type_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    leave_type = callback.data.split(":", 1)[1]
    await state.update_data(leave_type=leave_type)
    await state.set_state(LeaveRequest.waiting_start)
    await callback.message.edit_text(f"Tur: {leave_type}\n\n📅 Boshlanish sanasini kiriting (YYYY-MM-DD):")
    await callback.answer()


@router.message(LeaveRequest.waiting_start, F.text)
async def leave_start_date(message: Message, state: FSMContext) -> None:
    await state.update_data(start_date=message.text.strip())
    await state.set_state(LeaveRequest.waiting_end)
    await message.answer("📅 Tugash sanasini kiriting (YYYY-MM-DD):")


@router.message(LeaveRequest.waiting_end, F.text)
async def leave_end_date(message: Message, state: FSMContext) -> None:
    await state.update_data(end_date=message.text.strip())
    await state.set_state(LeaveRequest.waiting_reason)
    await message.answer("📝 Sababini qisqacha yozing:")


@router.message(LeaveRequest.waiting_reason, F.text)
async def leave_reason(message: Message, state: FSMContext, bot: Bot) -> None:
    employee = await db.get_employee_by_telegram_id(message.from_user.id)
    data = await state.get_data()
    leave_id = await db.add_leave_request(
        employee["id"], data["leave_type"], data["start_date"], data["end_date"], message.text.strip()
    )
    await state.clear()
    await message.answer("✅ So'rovingiz HR ga yuborildi. Javobni kuting.")

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🌴 Yangi ta'til so'rovi:\n\n"
                f"👤 {employee['full_name']}\n"
                f"📌 Tur: {data['leave_type']}\n"
                f"📅 {data['start_date']} — {data['end_date']}\n"
                f"📝 Sabab: {message.text.strip()}",
                reply_markup=kb.leave_decision_kb(leave_id),
            )
        except Exception:
            pass
