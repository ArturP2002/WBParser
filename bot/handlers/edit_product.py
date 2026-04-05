"""Обработчик редактирования товара"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from bot.states import EditProductStates
from database.repositories.task_repository import SearchTaskRepository
from bot.keyboards_all import (
    get_main_menu,
    get_edit_parameter_keyboard,
    get_product_action_keyboard,
)
from core.logger import logger

router = Router()


async def start_edit_product(message: Message, session: AsyncSession):
    """Начать редактирование товара - показать список"""
    from bot.handlers.list_products import list_products
    await list_products(message, session)


async def start_edit_task(
    callback: CallbackQuery,
    session: AsyncSession,
    task_id: int,
    state: FSMContext
):
    """Начать редактирование конкретной задачи - показать выбор параметров"""
    await callback.answer()
    
    # Сохранить task_id в состоянии
    await state.update_data(task_id=task_id)
    
    # Получить информацию о задаче
    task_repo = SearchTaskRepository(session)
    task = await task_repo.get_with_exclude_words(task_id)
    
    if not task:
        await callback.message.answer("Ошибка: задача не найдена")
        return
    
    exclude_words_text = ", ".join([ew.word for ew in task.exclude_words]) if task.exclude_words else "нет"
    
    text = (
        f"📦 Товар: {task.query}\n"
        f"💰 Диапазон цен: {task.price_min or 0}-{task.price_max or '∞'} руб\n"
        f"🚫 Исключения: {exclude_words_text}\n\n"
        f"Что вы хотите изменить?"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_edit_parameter_keyboard(task_id),
    )


@router.callback_query(lambda c: c.data.startswith("edit_name_"))
async def start_edit_name(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
):
    """Начать редактирование названия товара"""
    await callback.answer()
    task_id = int(callback.data.split("_")[2])
    
    await state.update_data(task_id=task_id)
    await state.set_state(EditProductStates.edit_name)
    
    await callback.message.edit_text(
        "📝 Введите новое название товара:",
    )


@router.message(EditProductStates.edit_name)
async def process_edit_name(
    message: Message,
    state: FSMContext,
    session: AsyncSession
):
    """Обработка редактирования названия товара"""
    try:
        data = await state.get_data()
        task_id = data.get("task_id")
        
        if not task_id:
            await message.answer("Ошибка: задача не выбрана")
            await state.clear()
            return
        
        new_query = message.text.strip()
        
        if not new_query:
            await message.answer("Название не может быть пустым. Попробуйте еще раз:")
            return
        
        task_repo = SearchTaskRepository(session)
        task = await task_repo.update(
            task_id=task_id,
            query=new_query,
        )
        
        if task:
            await message.answer(
                f"✅ Название обновлено: {new_query}",
                reply_markup=get_main_menu(),
            )
            logger.info(f"Task {task_id} query updated to: {new_query}")
        else:
            await message.answer("Ошибка: задача не найдена")
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error updating name: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обновлении названия. Попробуйте еще раз.")
        await state.clear()


@router.callback_query(lambda c: c.data.startswith("edit_price_"))
async def start_edit_price(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
):
    """Начать редактирование диапазона цен"""
    await callback.answer()
    task_id = int(callback.data.split("_")[2])
    
    await state.update_data(task_id=task_id)
    await state.set_state(EditProductStates.edit_price)
    
    await callback.message.edit_text(
        "💰 Введите новый диапазон цен в формате: 500-65000\n\n"
        "Пример: 1000-50000"
    )


@router.message(EditProductStates.edit_price)
async def process_edit_price(
    message: Message,
    state: FSMContext,
    session: AsyncSession
):
    """Обработка редактирования диапазона цен"""
    try:
        price_text = message.text.strip()
        
        if not price_text or "-" not in price_text:
            await message.answer("Неверный формат. Используйте: 500-65000")
            return
        
        price_min_str, price_max_str = price_text.split("-", 1)
        price_min = int(price_min_str.strip())
        price_max = int(price_max_str.strip())
        
        if price_min < 0 or price_max < 0:
            await message.answer("Цены не могут быть отрицательными. Попробуйте еще раз:")
            return
        
        if price_min > price_max:
            await message.answer("Минимальная цена не может быть больше максимальной. Попробуйте еще раз:")
            return
        
        data = await state.get_data()
        task_id = data.get("task_id")
        
        if not task_id:
            await message.answer("Ошибка: задача не выбрана")
            await state.clear()
            return
        
        task_repo = SearchTaskRepository(session)
        task = await task_repo.update(
            task_id=task_id,
            price_min=price_min,
            price_max=price_max,
        )
        
        if task:
            await message.answer(
                f"✅ Диапазон цен обновлен: {price_min}-{price_max} руб",
                reply_markup=get_main_menu(),
            )
            logger.info(f"Task {task_id} price range updated: {price_min}-{price_max}")
        else:
            await message.answer("Ошибка: задача не найдена")
        
        await state.clear()
        
    except ValueError:
        await message.answer("Неверный формат. Используйте числа: 500-65000")
    except Exception as e:
        logger.error(f"Error updating price: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обновлении цен. Попробуйте еще раз.")
        await state.clear()


@router.callback_query(lambda c: c.data.startswith("edit_exclude_"))
async def start_edit_exclude_words(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
):
    """Начать редактирование слов-исключений"""
    await callback.answer()
    task_id = int(callback.data.split("_")[2])
    
    await state.update_data(task_id=task_id)
    await state.set_state(EditProductStates.edit_exclude_words)
    
    # Получить текущие слова-исключения
    task_repo = SearchTaskRepository(session)
    task = await task_repo.get_with_exclude_words(task_id)
    
    current_words = ", ".join([ew.word for ew in task.exclude_words]) if task and task.exclude_words else "нет"
    
    await callback.message.edit_text(
        f"🚫 Текущие слова исключения: {current_words}\n\n"
        "Введите новые слова исключения через запятую:\n"
        "Пример: чехол, case, защита\n\n"
        "Чтобы удалить все слова исключения, отправьте пустое сообщение или 'нет'"
    )


@router.message(EditProductStates.edit_exclude_words)
async def process_edit_exclude_words(
    message: Message,
    state: FSMContext,
    session: AsyncSession
):
    """Обработка редактирования слов-исключений"""
    try:
        data = await state.get_data()
        task_id = data.get("task_id")
        
        if not task_id:
            await message.answer("Ошибка: задача не выбрана")
            await state.clear()
            return
        
        text = message.text.strip().lower()
        
        # Разрешить удаление с пустым сообщением или "нет"
        if not text or text == "нет" or text == "удалить":
            exclude_words = []
        else:
            exclude_words = [
                word.strip() 
                for word in text.split(",") 
                if word.strip()
            ]
        
        task_repo = SearchTaskRepository(session)
        task = await task_repo.update(
            task_id=task_id,
            exclude_words=exclude_words,
        )
        
        if task:
            words_text = ", ".join(exclude_words) if exclude_words else "нет"
            await message.answer(
                f"✅ Слова исключения обновлены: {words_text}",
                reply_markup=get_main_menu(),
            )
            logger.info(f"Task {task_id} exclude words updated: {exclude_words}")
        else:
            await message.answer("Ошибка: задача не найдена")
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error updating exclude words: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обновлении слов-исключений. Попробуйте еще раз.")
        await state.clear()
