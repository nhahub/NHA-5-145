"""Conservative name matching shared by recommendations and visible cart lines."""

import re


def product_name_tokens(text: str) -> str:
    text = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", text.casefold())
    text = text.translate(str.maketrans("أإآىة", "ااايه"))
    tokens = []
    for token in re.findall(r"\w+", text):
        token = token[2:] if token.startswith("ال") and len(token) > 3 else token
        # Common spellings of the garment type, not aliases for individual products.
        tokens.append("تيشيرت" if token == "تيشرت" else token)
    return " ".join(tokens)


def names_product(text: str, name: str) -> bool:
    normalized = product_name_tokens(name)
    return bool(normalized and f" {normalized} " in f" {product_name_tokens(text)} ")
