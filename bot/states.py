"""FSM states for bot flows.

This module consolidates all small `StatesGroup` definitions to reduce file
count on GitHub and simplify imports.
"""

from aiogram.fsm.state import State, StatesGroup


class AddProductStates(StatesGroup):
    """States for the add-product wizard."""

    query = State()  # Step 1: product name / search query
    price_range = State()  # Step 2: price range
    exclude_words = State()  # Step 3: words to exclude


class EditProductStates(StatesGroup):
    """States for the edit-product wizard."""

    waiting_for_edit = State()  # Waiting for user input (price/exclude words)
    edit_name = State()  # Edit product query/name
    edit_price = State()  # Edit price range
    edit_exclude_words = State()  # Edit exclude words

