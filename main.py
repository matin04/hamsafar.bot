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


from aiogram.fsm.state import State, StatesGroup

class SearchStates(StatesGroup):
    waiting_for_query = State()

@dp.message(F.text.lower() == "ҷустуҷӯи маршрут")
async def start_search(message: Message, state: FSMContext):
    await message.answer("Лутфан номи шаҳрро нависед (масалан: Душанбе):")
    await state.set_state(SearchStates.waiting_for_query)

@dp.message(SearchStates.waiting_for_query)
async def perform_search(message: Message, state: FSMContext):
    query = message.text.strip().lower()

    async with async_session() as session:
        result = await session.execute(select(Driver))
        drivers = result.scalars().all()

    matched = [d for d in drivers if query in d.trip.lower()]
    
    if not matched:
        await message.answer("Маршруте бо ин шаҳр ёфт нашуд.")
    else:
        for driver in matched:
            async with async_session() as session:
                user = await session.get(User, driver.user_id)

            text = (
                f"<-->Маршрут<--> \n"
                f"Ронанда: @{user.username}\n"
                f"Масир: {driver.trip}\n"
                f"Телефон: {user.phone}\n"
                f"Ҷойҳо: {driver.seats}"
            )
            await message.answer(text)

    await state.clear()



class ExtendedStates(StatesGroup):
    from_location = State()
    to_location = State()
    phone = State()
    seats = State()

@dp.message(F.text.lower() == 'добавить расширенный маршрут')
async def add_extended_trip(message: Message, state: FSMContext):
    await message.answer("Аз куҷо ҳаракат мекунед?")
    await state.set_state(ExtendedStates.from_location)

@dp.message(ExtendedStates.from_location)
async def set_from_location(message: Message, state: FSMContext):
    await state.update_data(from_location=message.text.strip())
    await message.answer("То куҷо меравад?")
    await state.set_state(ExtendedStates.to_location)

@dp.message(ExtendedStates.to_location)
async def set_to_location(message: Message, state: FSMContext):
    await state.update_data(to_location=message.text.strip())
    await message.answer("Рақами телефонро ворид кунед:")
    await state.set_state(ExtendedStates.phone)

@dp.message(ExtendedStates.phone)
async def set_phone_extended(message: Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    await message.answer("Чанд ҷойи холӣ ҳаст?")
    await state.set_state(ExtendedStates.seats)

@dp.message(ExtendedStates.seats)
async def finish_extended_trip(message: Message, state: FSMContext):
    data = await state.get_data()
    trip = f"{data['from_location']} - {data['to_location']}"
    seats = int(message.text.strip())

    async with async_session() as session:
        user = await session.scalar(select(User).filter_by(tg_id=message.from_user.id))
        if user:
            user.phone = data['phone']
            new_driver = Driver(
                user_id=user.id,
                trip=trip,
                seats=seats
            )
            session.add(new_driver)
            await session.commit()

    await message.answer(f"Маршрут {trip} бо {seats} ҷой илова шуд!")
    await state.clear()


class ConfirmRequestState(StatesGroup):
    awaiting = State()

pending_requests = {}  

@dp.callback_query(F.data.startswith("request_"))
async def handle_passenger_request(callback: CallbackQuery, state: FSMContext):
    driver_id = int(callback.data.split("_")[1])
    passenger_id = callback.from_user.id

    async with async_session() as session:
        driver = await session.get(Driver, driver_id)
        if not driver or driver.seats <= 0:
            await callback.message.answer("Ин маршрут дигар фаъол нест.")
            return
        user = await session.get(User, driver.user_id)

        if not user:
            await callback.message.answer("Ронанда нест.")
            return

        pending_requests[passenger_id] = driver_id

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Қабул мекунам", callback_data=f"accept_{passenger_id}"),
                InlineKeyboardButton(text="Рад мекунам", callback_data=f"decline_{passenger_id}")
            ]
        ])

        try:
            await bot.send_message(
                chat_id=user.tg_id,
                text=f"Клиент мехоҳад ба маршрут {driver.trip} биравад. Қабул мекунед?",
                reply_markup=kb
            )
        except:
            await callback.message.answer("Бо ронанда иртибот намешавад.")
            return

        await callback.message.answer("Запрос фиристода шуд.")

@dp.callback_query(F.data.startswith("accept_"))
async def accept_passenger(callback: CallbackQuery):
    passenger_id = int(callback.data.split("_")[1])
    driver_id = pending_requests.get(passenger_id)

    async with async_session() as session:
        driver = await session.get(Driver, driver_id)
        if driver:
            driver.seats -= 1
            if driver.seats <= 0:
                await session.delete(driver)
            await session.commit()

    await bot.send_message(passenger_id, "Ронанда шуморо қабул кард!")
    await callback.message.answer("Шумо пассажирро қабул кардед.")
    pending_requests.pop(passenger_id, None)

@dp.callback_query(F.data.startswith("decline_"))
async def decline_passenger(callback: CallbackQuery):
    passenger_id = int(callback.data.split("_")[1])
    await bot.send_message(passenger_id, "Ронанда шуморо рад кард.")
    await callback.message.answer("Шумо пассажирро рад кардед.")
    pending_requests.pop(passenger_id, None)


class ManageRequestStates(StatesGroup):
    waiting_for_driver = State()

@dp.callback_query(F.data.startswith("send_"))
async def send_request(callback: CallbackQuery, state: FSMContext):
    driver_id = int(callback.data.split("_")[1])
    passenger_id = callback.from_user.id

    async with async_session() as session:
        driver = await session.get(Driver, driver_id)
        passenger = await session.scalar(select(User).filter_by(tg_id=passenger_id))
        if not driver or driver.seats <= 0:
            await callback.message.answer("Ин маршрут дастнорас аст.")
            return

        driver_user = await session.get(User, driver.user_id)

        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Қабул", callback_data=f"confirm_accept_{passenger_id}_{driver_id}"),
                InlineKeyboardButton(text="Рад", callback_data=f"confirm_decline_{passenger_id}_{driver_id}")
            ]
        ])

        await bot.send_message(
            chat_id=driver_user.tg_id,
            text=f"@{passenger.username} мехоҳад ба маршрути шумо ({driver.trip}) ҳамроҳ шавад.",
            reply_markup=kb
        )

        await callback.message.answer("Дархост ба ронанда фиристода шуд.")
        await state.set_state(ManageRequestStates.waiting_for_driver)

@dp.callback_query(F.data.startswith("confirm_accept_"))
async def confirm_accept(callback: CallbackQuery):
    _, _, passenger_id_str, driver_id_str = callback.data.split("_")
    passenger_id = int(passenger_id_str)
    driver_id = int(driver_id_str)

    async with async_session() as session:
        driver = await session.get(Driver, driver_id)
        if not driver:
            await callback.message.answer("Маршрут дигар нест.")
            return

        driver.seats -= 1
        if driver.seats <= 0:
            await session.delete(driver)
        await session.commit()

    await bot.send_message(passenger_id, "Ронанда дархости шуморо қабул кард.")
    await callback.message.answer("Шумо дархостро қабул кардед.")

@dp.callback_query(F.data.startswith("confirm_decline_"))
async def confirm_decline(callback: CallbackQuery):
    _, _, passenger_id_str, driver_id_str = callback.data.split("_")
    passenger_id = int(passenger_id_str)

    await bot.send_message(passenger_id, "Ронанда дархости шуморо рад кард.")
    await callback.message.answer("Шумо дархостро рад кардед.")




@dp.message(F.text == "/Все маршруты с дополнительной информацией")
async def all_routes(message: Message):
    async with async_session() as session:
        result = await session.execute(select(Driver))
        routes = result.scalars().all()

        if not routes:
            await message.answer("Ҳеҷ як маршрут ёфт нашуд.")
            return

        for route in routes:
            user = await session.get(User, route.user_id)

            text = (
                f"<b>Маршрут</b>\n"
                f"Ронанда: @{user.username}\n"
                f"Телефон: {user.phone}\n"
                f"Масир: {route.trip}\n"
                f"Ҷойҳои холӣ: {route.seats}\n"
            )

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Отправить заявку", callback_data=f"request_{route.id}")]
            ])

            await message.answer(text, reply_markup=kb,)



@dp.message(F.text == "Все маршруты с дополнительной информацией")
async def show_all_routes_button(message: Message):
    await all_routes(message)  



@dp.message(F.text == "Маршрутҳои пуршуда")
async def show_full_routes(message: Message):
    async with async_session() as session:
        result = await session.execute(select(Driver).where(Driver.seats == 0))
        full_routes = result.scalars().all()

    if not full_routes:
        await message.answer("Ҳоло маршрутҳои пуршуда вуҷуд надоранд.")
        return

    for route in full_routes:
        user = await session.get(User, route.user_id)



        text = (
            f"<--> Маршрути пуршуда <-->\n"
            f"Ронанда: @{user.username}\n"
            f"Телефон: {user.phone}\n"
            f"Масир: {route.trip}\n"
            f"Ҷойҳои холӣ: {route.seats}\n"
        )

        await message.answer(text,)



async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
