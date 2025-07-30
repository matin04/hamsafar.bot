import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from sqlalchemy import select,update
from config import BOT_TOKEN
from db import Base, User, engine, async_session, Driver, Route
from random import choice
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class MyStates(StatesGroup):
    driver_trip = State()
    driver_seats = State()
    driver_phone = State()

kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='добовлять маршрут')],
    [KeyboardButton(text='Маршруты'),KeyboardButton(text='добавить расширенный маршрут')],
    [KeyboardButton(text="Все маршруты с дополнительной информацией"), KeyboardButton(text="ҷустуҷӯи маршрут")],
    

], resize_keyboard=True)

@dp.message(F.text == '/start')
async def start(message: Message, state: FSMContext):
    await message.answer("Добро пожаловать", reply_markup=kb)
    async with async_session() as session:
        user = await session.scalar(select(User).filter_by(tg_id=message.from_user.id))

        if not user:
            user = User(
                username=message.from_user.username,
                tg_id=message.from_user.id
            )
            session.add(user)
            await session.commit()
            await message.answer("Пожалуйста, отправьте свой номер телефона:")
            await state.set_state(MyStates.driver_phone)
        elif not user.phone:
            await message.answer("Пожалуйста, отправьте свой номер телефона:")
            await state.set_state(MyStates.driver_phone)

@dp.message(MyStates.driver_phone)
async def save_phone(message: Message, state: FSMContext):
    phone = message.text.strip()

    async with async_session() as session:
        user = await session.scalar(select(User).filter_by(tg_id=message.from_user.id))
        if user:
            user.phone = phone
            await session.commit()

    await message.answer("Номер телефона сохранён  виберите команду")
    await state.clear()

@dp.message(F.text == 'добовлять маршрут')
async def add_trip(message: Message, state: FSMContext):
    await message.answer("Введите маршрут (например: Душанбе-Москва):")
    await state.set_state(MyStates.driver_trip)

@dp.message(MyStates.driver_trip)
async def get_trip(message: Message, state: FSMContext):
    await state.update_data(trip=message.text.strip())
    await message.answer("Сколько свободных мест?")
    await state.set_state(MyStates.driver_seats)

@dp.message(MyStates.driver_seats)
async def get_seats_and_save(message: Message, state: FSMContext):
    data = await state.get_data()
    seats = int(message.text.strip())

    async with async_session() as session:
        user = await session.scalar(select(User).filter_by(tg_id=message.from_user.id))
        new_driver = Driver(
            user_id=user.id,
            trip=data['trip'],
            seats=seats
        )
        session.add(new_driver)
        await session.commit()

    await message.answer("Маршрут успешно добавлен!")
    await state.clear()

@dp.message(F.text == "Маршруты")
async def show_routes(message: Message):
    async with async_session() as session:
        result = await session.execute(select(Driver))
        drivers = result.scalars().all()

    if not drivers:
        await message.answer("Сейчас нет доступных маршрутов.")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=driver.trip, callback_data=f"trip_{driver.id}")]
            for driver in drivers
        ]
    )

    await message.answer("Доступные маршруты:", reply_markup=kb)

@dp.callback_query(F.data.startswith("trip_"))
async def route_selected(callback: CallbackQuery):
    driver_id = int(callback.data.split("_")[1])
    async with async_session() as session:
        driver = await session.get(Driver, driver_id)


        if not driver:
            await callback.message.answer("Маршрут больше не доступен.")
            return
        
        user = await session.get(User, driver.user_id)

        if not user:
            await callback.message.answer("Водитель больше не существует.")
            return

    text = (
        f"Маршрут: {driver.trip}\n"
        f"Водитель: @{user.username}\n"
        f"Телефон: {user.phone}\n"
        f"Осталось мест: {driver.seats}"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=" Отправить заявку", callback_data=f"request_{driver.id}")]
        ]
    )

    await callback.message.answer(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("request_"))
async def request_to_driver(callback: CallbackQuery):
    driver_id = int(callback.data.split("_")[1])

    async with async_session() as session:
        driver = await session.get(Driver, driver_id)

        if not driver:
            await callback.message.answer("Маршрут уже удалён.")
            return

        if driver.seats <= 0:
            await session.delete(driver)
            await session.commit()
            await callback.message.answer("Все места заняты. Маршрут удалён.")
            return

        driver.seats -= 1

        if driver.seats == 0:
            await session.delete(driver)
        await session.commit()

    await callback.message.answer("Вы записаны на маршрут!")
