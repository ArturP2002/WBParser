"""Product name normalizer for deduplication."""
import re
from typing import List


class ProductNormalizer:
    """Normalize product names for deduplication."""
    
    # Common colors to remove
    COLORS = [
        "blue", "black", "white", "red", "green", "yellow", "pink",
        "purple", "orange", "gray", "grey", "brown", "silver", "gold",
        "синий", "черный", "белый", "красный", "зеленый", "желтый",
        "розовый", "фиолетовый", "оранжевый", "серый", "коричневый",
        "серебристый", "золотой",
    ]
    
    # Words to remove
    STOP_WORDS = [
        "new", "sale", "promo", "акция", "новый", "распродажа",
        "original", "оригинал", "genuine", "подлинный",
    ]
    
    @staticmethod
    def normalize(name: str) -> str:
        """Normalize product name.
        
        Steps:
        1. Remove special characters
        2. Remove colors
        3. Remove stop words
        4. Lowercase
        5. Remove extra spaces
        """
        if not name:
            return ""
        
        # Lowercase
        normalized = name.lower()
        
        # Remove special characters (keep letters, numbers, spaces)
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        
        # Remove colors
        for color in ProductNormalizer.COLORS:
            # Word boundary match
            pattern = r'\b' + re.escape(color) + r'\b'
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # Remove stop words
        for word in ProductNormalizer.STOP_WORDS:
            pattern = r'\b' + re.escape(word) + r'\b'
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # Remove extra spaces
        normalized = re.sub(r'\s+', ' ', normalized)
        normalized = normalized.strip()
        
        return normalized
