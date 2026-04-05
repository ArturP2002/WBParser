"""Обработчик удаления товара"""
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.task_repository import SearchTaskRepository
from bot.keyboards_all import (
    get_confirm_keyboard,
    get_main_menu,
    get_product_list_keyboard,
)
from database.repositories.user_repository import UserRepository
from core.logger import logger


async def start_delete_product(message: Message, session: AsyncSession):
    """Начать удаление товара - показать список"""
    from bot.handlers.list_products import list_products
    await list_products(message, session)


async def confirm_delete_task(
    callback: CallbackQuery,
    session: AsyncSession,
    task_id: int
):
    """Показать подтверждение для удаления задачи"""
    task_repo = SearchTaskRepository(session)
    task = await task_repo.get_with_exclude_words(task_id)
    
    if not task:
        await callback.answer("Задача не найдена")
        return
    
    await callback.answer()
    await callback.message.edit_text(
        f"Вы уверены, что хотите удалить товар?\n\n"
        f"📦 {task.query}\n"
        f"💰 {task.price_min or 0}-{task.price_max or '∞'} руб",
        reply_markup=get_confirm_keyboard("delete", task_id),
    )


async def delete_task(
    callback: CallbackQuery,
    session: AsyncSession,
    task_id: int
):
    """Удалить задачу"""
    task_repo = SearchTaskRepository(session)
    deleted = await task_repo.delete(task_id)
    
    if deleted:
        await callback.answer("✅ Товар удален")
        await callback.message.edit_text(
            "✅ Товар успешно удален",
            reply_markup=None,
        )
        logger.info(f"Task {task_id} deleted")
    else:
        await callback.answer("❌ Ошибка при удалении")
