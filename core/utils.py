"""Утилиты для работы с данными"""
from typing import Optional, Tuple


def parse_price_range(price_text: str) -> Optional[Tuple[int, int]]:
    """Разбор диапазона цен из текста.
    
    Args:
        price_text: Текст диапазона цен (например, "500-65000")
    
    Returns:
        Кортеж из (price_min, price_max) или None, если невалидный
    """
    try:
        if "-" not in price_text:
            return None
        
        price_min_str, price_max_str = price_text.split("-", 1)
        price_min = int(price_min_str.strip())
        price_max = int(price_max_str.strip())
        
        if price_min < 0 or price_max < 0 or price_min >= price_max:
            return None
        
        return price_min, price_max
    except (ValueError, AttributeError):
        return None


def parse_exclude_words(words_text: str) -> list[str]:
    """Разбор слов исключения из текста.
    
    Args:
        words_text: Разделенные запятой слова (например, "чехол,case,glass")
    
    Returns:
        Список слов
    """
    if not words_text or words_text.strip().lower() == "пропустить":
        return []
    
    return [word.strip() for word in words_text.split(",") if word.strip()]
