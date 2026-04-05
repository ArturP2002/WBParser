"""Пользовательские исключения для приложения"""


class WBParserError(Exception):
    """Базовое исключение для ошибок парсера"""
    pass


class ParserError(WBParserError):
    """Ошибка в операциях парсера"""
    pass


class DatabaseError(WBParserError):
    """Ошибка в операциях базы данных"""
    pass


class NotificationError(WBParserError):
    """Ошибка в операциях уведомлений"""
    pass


class WBAPIError(ParserError):
    """Ошибка в запросах API Wildberries"""
    pass


class ValidationError(WBParserError):
    """Ошибка валидации"""
    pass


class RateLimitError(NotificationError):
    """Превышение лимита скорости"""
    pass
