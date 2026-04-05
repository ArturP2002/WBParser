"""Обработчик списка товаров"""
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.user_repository import UserRepository
from database.repositories.task_repository import SearchTaskRepository
from bot.keyboards_all import get_product_list_keyboard, get_product_action_keyboard
from core.logger import logger


async def list_products(message: Message, session: AsyncSession):
    """Показать все товары пользователя"""
    user_repo = UserRepository(session)
    task_repo = SearchTaskRepository(session)
    
    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return
    
    tasks = await task_repo.get_by_user(user.id)
    
    if not tasks:
        await message.answer("У вас пока нет отслеживаемых товаров.")
        return
    
    text = "📋 Ваши отслеживаемые товары:\n\n"
    for i, task in enumerate(tasks, 1):
        status = "✅" if task.is_active else "⏸"
        text += f"{i}. {status} {task.query}\n"
        text += f"   Цена: {task.price_min or 0}-{task.price_max or '∞'} руб\n\n"
    
    await message.answer(
        text,
        reply_markup=get_product_list_keyboard(tasks),
    )


async def show_task_details(
    callback: CallbackQuery,
    session: AsyncSession,
    task_id: int
):
    """Показать подробную информацию о задаче"""
    task_repo = SearchTaskRepository(session)
    task = await task_repo.get_with_exclude_words(task_id)
    
    if not task:
        await callback.answer("Задача не найдена")
        return
    
    exclude_words = ", ".join([ew.word for ew in task.exclude_words]) if task.exclude_words else "нет"
    
    text = (
        f"📦 Товар: {task.query}\n"
        f"💰 Диапазон цен: {task.price_min or 0}-{task.price_max or '∞'} руб\n"
        f"🚫 Исключения: {exclude_words}\n"
        f"📊 Статус: {'Активен' if task.is_active else 'Приостановлен'}\n"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_product_action_keyboard(task_id),
    )
