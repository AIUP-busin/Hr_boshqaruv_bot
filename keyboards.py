from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# ---------- Reply menus ----------

ADMIN_MENU = [
    "👥 Xodimlar",
    "🆕 Yangi so'rovlar",
    "🌴 Ta'til so'rovlari",
    "✅ Vazifa berish",
    "📋 Vazifalar holati",
    "📢 E'lon yuborish",
    "💰 Maosh belgilash",
    "📊 Hisobot",
]

EMPLOYEE_MENU = [
    "✅ Keldim",
    "🚪 Ketdim",
    "🌴 Ta'til so'rash",
    "📜 Ta'til tarixim",
    "📋 Mening vazifalarim",
    "💰 Mening maoshim",
    "👤 Profilim",
]


def admin_main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for label in ADMIN_MENU:
        builder.button(text=label)
    builder.adjust(2, 2, 2, 2)
    return builder.as_markup(resize_keyboard=True)


def employee_main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for label in EMPLOYEE_MENU:
        builder.button(text=label)
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


def phone_request_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Telefon raqamni yuborish", request_contact=True)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


# ---------- Inline keyboards ----------

def approve_reject_kb(employee_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data=f"emp_approve:{employee_id}")
    builder.button(text="❌ Rad etish", callback_data=f"emp_reject:{employee_id}")
    builder.adjust(2)
    return builder.as_markup()


def leave_decision_kb(leave_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data=f"leave_approve:{leave_id}")
    builder.button(text="❌ Rad etish", callback_data=f"leave_reject:{leave_id}")
    builder.adjust(2)
    return builder.as_markup()


def employee_picker_kb(employees: list[dict], prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for emp in employees:
        builder.button(text=emp["full_name"], callback_data=f"{prefix}:{emp['id']}")
    builder.adjust(1)
    return builder.as_markup()


def employee_manage_kb(employee_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 O'chirish", callback_data=f"emp_delete:{employee_id}")
    builder.adjust(1)
    return builder.as_markup()


def task_done_kb(task_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Bajarildi deb belgilash", callback_data=f"task_done:{task_id}")
    builder.adjust(1)
    return builder.as_markup()


def webapp_inline_kb(url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Mini ilovani ochish", web_app=WebAppInfo(url=url))
    return builder.as_markup()


def leave_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🌴 Ta'til", callback_data="leave_type:Ta'til")
    builder.button(text="🤒 Bemorlik", callback_data="leave_type:Bemorlik")
    builder.button(text="📝 Boshqa", callback_data="leave_type:Boshqa")
    builder.adjust(1)
    return builder.as_markup()
