"""Product filters."""
from typing import List
import re
from parser.wb.wb_models import WBProduct
from database.models.search_task import SearchTask
from database.models.task_exclude_word import TaskExcludeWord
from core.logger import logger


def contains_excluded_words(
    product: WBProduct, 
    exclude_words: List[TaskExcludeWord]
) -> bool:
    """Check if product contains excluded words."""
    if not exclude_words:
        return False
    
    product_name_lower = product.name.lower()
    
    for exclude_word in exclude_words:
        if exclude_word.word.lower() in product_name_lower:
            return True
    
    return False


def is_relevant_to_query(product: WBProduct, query: str) -> bool:
    """Check if product name contains query keywords (relevance filter).
    
    For single-word queries: requires exact word match (as whole word).
    For multi-word queries: requires at least 50% of significant words (or min 2 words).
    
    Args:
        product: Product to check
        query: Search query string
    
    Returns:
        True if product is relevant, False otherwise
    """
    if not query or not product.name:
        return True  # If no query, don't filter
    
    # Normalize: lowercase, remove special chars
    query_lower = query.lower().strip()
    product_name_lower = product.name.lower()
    
    # Split query into words (remove punctuation, split by spaces)
    query_words = re.findall(r'\b\w+\b', query_lower)
    
    # Filter out very short words (likely not significant)
    significant_words = [w for w in query_words if len(w) >= 3]
    
    # If no significant words, check if whole query is in name as whole word
    if not significant_words:
        # For short queries, require whole word match
        pattern = r'\b' + re.escape(query_lower) + r'\b'
        return bool(re.search(pattern, product_name_lower))
    
    # For multi-word queries: require at least 50% of words (or minimum 2 words)
    # This is more flexible than "all words" - allows for variations in product names
    matched_words = 0
    for word in significant_words:
        # Use word boundary to avoid partial matches (e.g., "iphone" in "smartphone")
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, product_name_lower):
            matched_words += 1
    
    # Calculate threshold: at least 50% or minimum 2 words (if query has 3+ words)
    total_words = len(significant_words)
    if total_words <= 2:
        # For 1-2 words, require all
        threshold = total_words
    else:
        # For 3+ words, require at least 50% or minimum 2
        threshold = max(2, int(total_words * 0.5) + (1 if total_words % 2 == 1 else 0))
    
    is_relevant = matched_words >= threshold
    
    if not is_relevant:
        logger.debug(
            f"Product filtered by relevance: '{product.name}' "
            f"(matched {matched_words}/{total_words} words from query: '{query}')"
        )
    
    return is_relevant


def price_in_range(
    product: WBProduct,
    price_min: int,
    price_max: int,
) -> bool:
    """Check if product price is in range."""
    if price_min is None or price_max is None:
        return True

    # Если цена неизвестна, товар не может быть подтверждён по диапазону цен.
    if product.price is None:
        return False

    return price_min <= product.price <= price_max


def filter_products(
    products: List[WBProduct],
    task: SearchTask,
) -> List[WBProduct]:
    """Filter products by task criteria.
    
    Args:
        products: List of products to filter
        task: Search task with criteria
    
    Returns:
        Filtered list of products
    """
    filtered = []
    relevance_filtered = 0
    excluded_filtered = 0
    price_filtered = 0
    
    for product in products:
        # Check relevance to query (must contain query keywords)
        if not is_relevant_to_query(product, task.query):
            relevance_filtered += 1
            continue
        
        # Check excluded words
        if contains_excluded_words(product, task.exclude_words):
            excluded_filtered += 1
            continue
        
        # Check price range
        if not price_in_range(product, task.price_min, task.price_max):
            price_filtered += 1
            continue
        
        filtered.append(product)
    
    # Log filtering statistics
    if relevance_filtered > 0 or excluded_filtered > 0 or price_filtered > 0:
        logger.info(
            f"Filtering stats for query '{task.query}': "
            f"{len(filtered)} passed, "
            f"{relevance_filtered} filtered by relevance, "
            f"{excluded_filtered} filtered by exclude words, "
            f"{price_filtered} filtered by price range"
        )
    
    return filtered
