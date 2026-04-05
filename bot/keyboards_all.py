"""Combined inline/reply keyboards for the Telegram bot.

This consolidates multiple small keyboard modules into one file to reduce
GitHub file count.
"""

from typing import List

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from database.models.search_task import SearchTask


def get_main_menu() -> ReplyKeyboardMarkup:
    """Main reply keyboard."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Добавить товар")],
            [KeyboardButton(text="📋 Изменить товар")],
            [
                KeyboardButton(text="➕ Массовое добавление"),
                KeyboardButton(text="✏ Массовое редактирование"),
            ],
            [
                KeyboardButton(text="📊 Таблица цен"),
                KeyboardButton(text="🗑 Удалить товар"),
            ],
        ],
        resize_keyboard=True,
    )
    return keyboard


def get_product_list_keyboard(tasks: List[SearchTask]) -> InlineKeyboardMarkup:
    """Inline keyboard for a list of tasks."""
    buttons = []
    for task in tasks:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=task.query,
                    callback_data=f"task_{task.id}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_product_action_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Inline keyboard with actions for a single task."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏ Редактировать",
                    callback_data=f"edit_task_{task_id}",
                ),
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"delete_task_{task_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data="back_to_list",
                ),
            ],
        ]
    )
    return keyboard


def get_edit_parameter_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Inline keyboard to choose which parameter to edit."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Название",
                    callback_data=f"edit_name_{task_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💰 Диапазон цен",
                    callback_data=f"edit_price_{task_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Слова исключения",
                    callback_data=f"edit_exclude_{task_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=f"task_{task_id}",
                ),
            ],
        ]
    )
    return keyboard


def get_confirm_keyboard(action: str, item_id: int) -> InlineKeyboardMarkup:
    """Confirmation keyboard for destructive actions."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да",
                    callback_data=f"confirm_{action}_{item_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Нет",
                    callback_data=f"cancel_{action}_{item_id}",
                ),
            ],
        ]
    )
    return keyboard


__all__ = [
    "get_main_menu",
    "get_product_list_keyboard",
    "get_product_action_keyboard",
    "get_edit_parameter_keyboard",
    "get_confirm_keyboard",
]

