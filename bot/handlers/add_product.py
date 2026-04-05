"""Обработчик добавления товара"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from bot.states import AddProductStates
from database.repositories.user_repository import UserRepository
from database.repositories.task_repository import SearchTaskRepository
from bot.services.task_service import TaskService
from bot.keyboards_all import get_main_menu
from core.logger import logger

router = Router()


async def start_add_product(message: Message, state: FSMContext):
    """Начать добавление товара"""
    await state.set_state(AddProductStates.query)
    await message.answer(
        "Шаг 1 из 3: Введите название товара для поиска\n\n"
        "Пример: iPhone 17 256GB"
    )


@router.message(F.text, AddProductStates.query)
async def process_query(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка запроса на добавление товара"""
    query = message.text.strip()
    
    if len(query) < 3:
        await message.answer("Название товара должно быть не менее 3 символов")
        return
    
    await state.update_data(query=query)
    await state.set_state(AddProductStates.price_range)
    
    await message.answer(
        "Шаг 2 из 3: Введите диапазон цен\n\n"
        "Формат: минимальная-максимальная\n"
        "Пример: 500-65000"
    )


@router.message(F.text, AddProductStates.price_range)
async def process_price_range(
    message: Message, 
    state: FSMContext, 
    session: AsyncSession
):
    """Обработка диапазона цен"""
    try:
        price_text = message.text.strip()
        if "-" not in price_text:
            raise ValueError("Неверный формат")
        
        price_min_str, price_max_str = price_text.split("-", 1)
        price_min = int(price_min_str.strip())
        price_max = int(price_max_str.strip())
        
        if price_min < 0 or price_max < 0:
            raise ValueError("Цена не может быть отрицательной")
        if price_min >= price_max:
            raise ValueError("Минимальная цена должна быть меньше максимальной")
        
        await state.update_data(price_min=price_min, price_max=price_max)
        await state.set_state(AddProductStates.exclude_words)
        
        await message.answer(
            "Шаг 3 из 3: Введите слова для исключения (опционально)\n\n"
            "Формат: слово1,слово2,слово3\n"
            "Пример: чехол,case,glass\n\n"
            "Или отправьте 'пропустить' для пропуска этого шага"
        )
        
    except ValueError as e:
        await message.answer(f"Ошибка: {e}\n\nПопробуйте еще раз в формате: 500-65000")


@router.message(F.text, AddProductStates.exclude_words)
async def process_exclude_words(
    message: Message, 
    state: FSMContext, 
    session: AsyncSession
):
    """Обработка слов для исключения"""
    data = await state.get_data()
    query = data.get("query")
    price_min = data.get("price_min")
    price_max = data.get("price_max")
    
    exclude_words = []
    if message.text.strip().lower() != "пропустить":
        exclude_words = [
            word.strip() 
            for word in message.text.split(",") 
            if word.strip()
        ]
    
    # Get user
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(message.from_user.id)
    
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        await state.clear()
        return
    
    # Check task limit
    task_service = TaskService(session)
    if not await task_service.check_task_limit(user.id):
        await message.answer(
            "Достигнут лимит задач (100). Удалите старые задачи для добавления новых."
        )
        await state.clear()
        return
    
    # Create task
    task_repo = SearchTaskRepository(session)
    task = await task_repo.create(
        user_id=user.id,
        query=query,
        price_min=price_min,
        price_max=price_max,
        exclude_words=exclude_words,
    )
    
    await state.clear()
    
    await message.answer(
        f"✅ Товар успешно добавлен!\n\n"
        f"Название: {query}\n"
        f"Диапазон цен: {price_min}-{price_max} руб\n"
        f"Исключения: {', '.join(exclude_words) if exclude_words else 'нет'}\n\n"
        f"Мониторинг начат.",
        reply_markup=get_main_menu(),
    )
    
    logger.info(f"Task created: {task.id} for user {user.id}")
