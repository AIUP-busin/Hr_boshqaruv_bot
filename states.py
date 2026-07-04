from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    waiting_name = State()
    waiting_phone = State()


class ApproveEmployee(StatesGroup):
    waiting_position = State()
    waiting_department = State()
    waiting_salary = State()


class LeaveRequest(StatesGroup):
    waiting_type = State()
    waiting_start = State()
    waiting_end = State()
    waiting_reason = State()


class Broadcast(StatesGroup):
    waiting_text = State()


class TaskAssign(StatesGroup):
    waiting_employee = State()
    waiting_title = State()
    waiting_description = State()
    waiting_deadline = State()


class SalaryEdit(StatesGroup):
    waiting_employee = State()
    waiting_amount = State()
