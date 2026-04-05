"""Combined Telegram routers.

This file consolidates multiple small router modules to reduce GitHub file
count. It exposes the same router objects that `main.py` expects:
`start_router`, `menu_router`, `product_router`.
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.user_repository import UserRepository
from bot.keyboards_all import get_main_menu, get_product_list_keyboard
from core.logger import logger


start_router = Router()
menu_router = Router()
product_router = Router()


@start_router.message(Command("start"))
async def cmd_start(message: Message, session: AsyncSession):
    """Обработка команды /start"""
    user_repo = UserRepository(session)

    # Получить или создать пользователя
    user, created = await user_repo.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
    )

    if created:
        logger.info(f"New user registered: {user.telegram_id}")

    welcome_text = (
        "👋 Добро пожаловать в парсер Wildberries!\n\n"
        "Я помогу вам отслеживать товары по заданным критериям.\n\n"
        "Используйте меню для управления товарами."
    )

    await message.answer(
        welcome_text,
        reply_markup=get_main_menu(),
    )


@menu_router.message(lambda m: m.text == "📦 Добавить товар")
async def add_product_handler(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
):
    """Обработка кнопки добавления товара"""
    from bot.handlers.add_product import start_add_product

    await start_add_product(message, state)


@menu_router.message(lambda m: m.text == "📋 Изменить товар")
async def edit_product_handler(message: Message, session: AsyncSession):
    """Обработка кнопки редактирования товара"""
    from bot.handlers.edit_product import start_edit_product

    await start_edit_product(message, session)


@menu_router.message(lambda m: m.text == "🗑 Удалить товар")
async def delete_product_handler(message: Message, session: AsyncSession):
    """Обработка кнопки удаления товара"""
    from bot.handlers.delete_product import start_delete_product

    await start_delete_product(message, session)


@menu_router.message(lambda m: m.text == "📋 Список товаров")
async def list_products_handler(message: Message, session: AsyncSession):
    """Обработка кнопки списка товаров"""
    from bot.handlers.list_products import list_products

    await list_products(message, session)


@menu_router.message(lambda m: m.text == "📊 Таблица цен")
async def price_table_handler(message: Message, session: AsyncSession):
    """Обработка кнопки таблицы цен"""
    await message.answer("Функция в разработке")


@menu_router.message(lambda m: m.text in ["➕ Массовое добавление", "✏ Массовое редактирование"])
async def bulk_operations_handler(message: Message, session: AsyncSession):
    """Обработка кнопок массового добавления и редактирования"""
    await message.answer("Функция в разработке")


@product_router.callback_query(lambda c: c.data.startswith("task_"))
async def task_callback(callback: CallbackQuery, session: AsyncSession):
    """Обработка выбора товара"""
    task_id = int(callback.data.split("_")[1])
    from bot.handlers.list_products import show_task_details

    await show_task_details(callback, session, task_id)


@product_router.callback_query(lambda c: c.data.startswith("edit_task_"))
async def edit_task_callback(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    """Обработка кнопки редактирования товара"""
    task_id = int(callback.data.split("_")[2])
    from bot.handlers.edit_product import start_edit_task

    await start_edit_task(callback, session, task_id, state)


@product_router.callback_query(lambda c: c.data.startswith("delete_task_"))
async def delete_task_callback(callback: CallbackQuery, session: AsyncSession):
    """Обработка кнопки удаления товара"""
    task_id = int(callback.data.split("_")[2])
    from bot.handlers.delete_product import confirm_delete_task

    await confirm_delete_task(callback, session, task_id)


@product_router.callback_query(lambda c: c.data.startswith("confirm_delete_"))
async def confirm_delete_callback(callback: CallbackQuery, session: AsyncSession):
    """Обработка подтверждения удаления товара"""
    task_id = int(callback.data.split("_")[2])
    from bot.handlers.delete_product import delete_task

    await delete_task(callback, session, task_id)


@product_router.callback_query(lambda c: c.data == "back_to_list")
async def back_to_list_callback(callback: CallbackQuery, session: AsyncSession):
    """Обработка кнопки возврата к списку товаров"""
    await callback.answer()

    # Delete current message
    await callback.message.delete()

    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.bot.send_message(
            callback.from_user.id, "Ошибка: пользователь не найден"
        )
        return

    from database.repositories.task_repository import SearchTaskRepository

    task_repo = SearchTaskRepository(session)
    tasks = await task_repo.get_by_user(user.id)

    if not tasks:
        await callback.bot.send_message(
            callback.from_user.id, "У вас пока нет отслеживаемых товаров."
        )
        return

    text = "📋 Ваши отслеживаемые товары:\n\n"
    for i, task in enumerate(tasks, 1):
        status = "✅" if task.is_active else "⏸"
        text += f"{i}. {status} {task.query}\n"
        text += f"   Цена: {task.price_min or 0}-{task.price_max or '∞'} руб\n\n"

    await callback.bot.send_message(
        callback.from_user.id,
        text,
        reply_markup=get_product_list_keyboard(tasks),
    )


@product_router.callback_query(lambda c: c.data.startswith("cancel_"))
async def cancel_callback(callback: CallbackQuery):
    """Обработка отмены"""
    await callback.answer("Отменено")
    await callback.message.delete()

