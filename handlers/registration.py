from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

import database as db
import keyboards as kb
from config import ADMIN_IDS, WEBAPP_URL
from states import ApproveEmployee, Registration

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    telegram_id = message.from_user.id

    if telegram_id in ADMIN_IDS:
        await message.answer(
            "👋 Xush kelibsiz, HR admin!\nQuyidagi menyudan foydalaning.",
            reply_markup=kb.admin_main_menu(),
        )
        if WEBAPP_URL:
            await message.answer(
                "Yoki qulay Mini App orqali boshqaring:",
                reply_markup=kb.webapp_inline_kb(WEBAPP_URL),
            )
        return

    employee = await db.get_employee_by_telegram_id(telegram_id)

    if employee is None:
        await message.answer(
            "👋 Assalomu alaykum! HR boshqaruv botiga xush kelibsiz.\n\n"
            "Ro'yxatdan o'tish uchun to'liq ism-familiyangizni yuboring:",
            reply_markup=ReplyKeyboardRemove(),
        )
        await state.set_state(Registration.waiting_name)
        return

    if employee["status"] == "approved":
        await message.answer(
            f"👋 Xush kelibsiz, {employee['full_name']}!",
            reply_markup=kb.employee_main_menu(),
        )
        if WEBAPP_URL:
            await message.answer(
                "Yoki qulay Mini App orqali foydalaning:",
                reply_markup=kb.webapp_inline_kb(WEBAPP_URL),
            )
    elif employee["status"] == "pending":
        await message.answer(
            "⏳ So'rovingiz HR tomonidan hali ko'rib chiqilmoqda. Iltimos, kuting."
        )
    else:  # rejected
        await message.answer(
            "❌ Avvalgi so'rovingiz rad etilgan edi. Qayta urinish uchun "
            "to'liq ism-familiyangizni yuboring:",
            reply_markup=ReplyKeyboardRemove(),
        )
        await state.set_state(Registration.waiting_name)


@router.message(Registration.waiting_name, F.text)
async def registration_name(message: Message, state: FSMContext) -> None:
    await state.update_data(full_name=message.text.strip())
    await message.answer(
        "📱 Endi telefon raqamingizni yuboring (tugmani bosing):",
        reply_markup=kb.phone_request_menu(),
    )
    await state.set_state(Registration.waiting_phone)


@router.message(Registration.waiting_phone, F.contact)
async def registration_phone_contact(message: Message, state: FSMContext, bot: Bot) -> None:
    await _finish_registration(message, state, bot, message.contact.phone_number)


@router.message(Registration.waiting_phone, F.text)
async def registration_phone_text(message: Message, state: FSMContext, bot: Bot) -> None:
    await _finish_registration(message, state, bot, message.text.strip())


async def _finish_registration(message: Message, state: FSMContext, bot: Bot, phone: str) -> None:
    data = await state.get_data()
    full_name = data.get("full_name", "Noma'lum")
    telegram_id = message.from_user.id

    existing = await db.get_employee_by_telegram_id(telegram_id)
    if existing:
        await db.resubmit_registration(existing["id"], full_name, phone)
        employee_id = existing["id"]
    else:
        employee_id = await db.add_pending_employee(telegram_id, full_name, phone)

    await state.clear()
    await message.answer(
        "✅ So'rovingiz yuborildi! HR admin ko'rib chiqib, sizga xabar beradi.",
        reply_markup=ReplyKeyboardRemove(),
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🆕 Yangi xodim so'rovi:\n\n"
                f"👤 Ism: {full_name}\n"
                f"📱 Tel: {phone}\n\n"
                f"Tasdiqlaysizmi?",
                reply_markup=kb.approve_reject_kb(employee_id),
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("emp_approve:"))
async def approve_start(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    employee_id = int(callback.data.split(":")[1])
    await state.update_data(employee_id=employee_id)
    await state.set_state(ApproveEmployee.waiting_position)
    await callback.message.answer("💼 Lavozimini kiriting:")
    await callback.answer()


@router.message(ApproveEmployee.waiting_position, F.text)
async def approve_position(message: Message, state: FSMContext) -> None:
    await state.update_data(position=message.text.strip())
    await state.set_state(ApproveEmployee.waiting_department)
    await message.answer("🏢 Bo'limini kiriting:")


@router.message(ApproveEmployee.waiting_department, F.text)
async def approve_department(message: Message, state: FSMContext) -> None:
    await state.update_data(department=message.text.strip())
    await state.set_state(ApproveEmployee.waiting_salary)
    await message.answer("💰 Oylik maoshini kiriting (faqat son, so'mda):")


@router.message(ApproveEmployee.waiting_salary, F.text)
async def approve_salary(message: Message, state: FSMContext, bot: Bot) -> None:
    try:
        salary = float(message.text.strip().replace(" ", "").replace(",", "."))
    except ValueError:
        await message.answer("❗ Iltimos, faqat son kiriting. Masalan: 4000000")
        return

    data = await state.get_data()
    employee_id = data["employee_id"]
    position = data["position"]
    department = data["department"]

    await db.approve_employee(employee_id, position, department, salary)
    await state.clear()

    employee = await db.get_employee_by_id(employee_id)
    await message.answer(f"✅ {employee['full_name']} tasdiqlandi va tizimga qo'shildi.")

    try:
        await bot.send_message(
            employee["telegram_id"],
            f"🎉 Tabriklaymiz! So'rovingiz tasdiqlandi.\n\n"
            f"💼 Lavozim: {position}\n"
            f"🏢 Bo'lim: {department}\n\n"
            f"Endi botdan to'liq foydalanishingiz mumkin.",
            reply_markup=kb.employee_main_menu(),
        )
        if WEBAPP_URL:
            await bot.send_message(
                employee["telegram_id"],
                "Yoki qulay Mini App orqali foydalaning:",
                reply_markup=kb.webapp_inline_kb(WEBAPP_URL),
            )
    except Exception:
        pass


@router.callback_query(F.data.startswith("emp_reject:"))
async def reject_employee_cb(callback: CallbackQuery, bot: Bot) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    employee_id = int(callback.data.split(":")[1])
    employee = await db.get_employee_by_id(employee_id)
    await db.reject_employee(employee_id)
    await callback.message.edit_text(f"❌ {employee['full_name']} so'rovi rad etildi.")
    await callback.answer()

    try:
        await bot.send_message(
            employee["telegram_id"],
            "❌ Afsuski, so'rovingiz rad etildi. Qayta urinish uchun /start bosing.",
        )
    except Exception:
        pass
