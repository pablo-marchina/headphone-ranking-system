from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


ACCESSORY_KEYWORDS = (
    "almofada", "earpad", "ear pad", "capa", "case", "bolsa", "estojo",
    "cabo", "carregador", "fonte", "adaptador", "suporte", "pelicula",
    "filtro", "protetor", "plug", "conector", "ponta", "espuma",
    "replacement", "reposicao", "reposicao", "peca", "peça", "acessorio",
    "acessorio", "kit", "stand", "cover",
)

CONDITION_KEYWORDS = {
    "new": ("novo", "nova", "new", "lacrado"),
    "used": ("usado", "usada", "semi novo", "seminovo", "refurbished", "renewed"),
}

VARIANT_REMOVE_PATTERNS = (
    r"\bsample\s+\d+\b",
    r"\bserial\s+number\s+\w+\b",
    r"\bwith\b.*\b(filter|filters|earpads|pads)\b",
    r"\b\([^)]*(sample|serial|filter|filters|earpads|pads)[^)]*\)",
    r"\b(filter|filters|earpads|pads)\b",
    r"\bflat\s+eq\b",
    r"\bparametric\s+eq\b",
    r"\bgraphic\s+eq\b",
)

COMMERCIAL_NOISE_PATTERNS = (
    r"\bdefault\s+mode\b",
    r"\bbass\+\b",
    r"\bbass\b",
    r"\bpost[- ]?2020\b",
    r"\bpost[- ]?2020\s+earpads\b",
    r"\batmospheric\s+immersion\s+mode\b",
    r"\bfoam\s+eartips\b",
    r"\bfoam\s+tips\b",
    r"\bfit\s+test\b",
    r"\btuning\b",
)

CORE_DROP_TOKENS = {
    "headphone", "headphones", "fone", "fones", "earbuds", "earbud", "iem",
    "bluetooth", "wireless", "wired", "anc", "active", "passive", "mode",
    "default", "flat", "bass", "plus", "eq", "edition",
}

PROTECTED_MODEL_TOKENS = {
    "pro", "ultra", "max", "plus", "dsp", "mk2", "mk3", "mkii", "mkiii",
    "ii", "iii", "iv", "v", "hd", "ie", "dt", "red", "blue", "black",
}

VARIANT_GROUP_PATTERNS = {
    "wireless": r"\bwireless\b",
    "wired": r"\bwired\b",
    "anc": r"\banc\b",
    "bluetooth": r"\bbluetooth\b",
    "passive": r"\bpassive\b",
    "active": r"\bactive\b",
}

GENERIC_BRANDS = {
    "sony", "sennheiser", "bose", "jbl", "akg", "beats", "hifiman",
    "beyerdynamic", "audio technica", "audio-technica", "moondrop",
    "truthear", "edifier", "anker", "kz", "fiio", "focal",
}


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> list[str]:
    return [token for token in normalize_text(text).split() if token]


def infer_variant_group(name: str) -> str:
    normalized = normalize_text(name)
    matched = [key for key, pattern in VARIANT_GROUP_PATTERNS.items() if re.search(pattern, normalized)]
    return "+".join(sorted(matched)) if matched else "base"


def canonicalize_headphone_name(name: str) -> str:
    text = normalize_text(name)
    for pattern in VARIANT_REMOVE_PATTERNS:
        text = re.sub(pattern, " ", text)
    text = re.sub(r"\b(anc on|anc off)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def commercial_search_name(name: str) -> str:
    text = canonicalize_headphone_name(name)
    text = re.sub(r"\b(active|passive)\b", " ", text)
    text = re.sub(r"\b(anc|wired|wireless|bluetooth)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def ultra_commercial_search_name(name: str) -> str:
    text = commercial_search_name(name)
    for pattern in COMMERCIAL_NOISE_PATTERNS:
        text = re.sub(pattern, " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def model_core_search_name(name: str) -> str:
    base = ultra_commercial_search_name(name)
    tokens = tokenize(base)
    if not tokens:
        return base

    brand = infer_brand(base)
    keep: list[str] = []
    for idx, token in enumerate(tokens):
        is_brand_token = bool(brand and idx == 0 and token in set(brand.split()))
        has_digit = bool(re.search(r"\d", token))
        protected = token in PROTECTED_MODEL_TOKENS
        if is_brand_token or has_digit or protected:
            keep.append(token)
            continue
        if token in CORE_DROP_TOKENS:
            continue
        if len(tokens) <= 3:
            keep.append(token)

    if brand:
        brand_tokens = brand.split()
        for token in reversed(brand_tokens):
            if token in keep:
                keep.remove(token)
        keep = brand_tokens + keep

    deduped: list[str] = []
    for token in keep:
        if token not in deduped:
            deduped.append(token)
    return " ".join(deduped).strip() or base


def infer_condition(text: str) -> str:
    normalized = normalize_text(text)
    if any(keyword in normalized for keyword in CONDITION_KEYWORDS["used"]):
        return "used"
    if any(keyword in normalized for keyword in CONDITION_KEYWORDS["new"]):
        return "new"
    return "unknown"


def is_accessory_title(title: str) -> bool:
    normalized = normalize_text(title)
    return any(keyword in normalized for keyword in ACCESSORY_KEYWORDS)


def infer_brand(name: str) -> str:
    normalized = normalize_text(name)
    for brand in sorted(GENERIC_BRANDS, key=len, reverse=True):
        if normalized.startswith(brand):
            return brand
    tokens = tokenize(normalized)
    return tokens[0] if tokens else ""


@dataclass(frozen=True)
class MatchResult:
    canonical_name: str
    display_name: str
    title: str
    match_score: float
    is_accessory: bool
    variant_conflict: bool
    condition: str
    brand_conflict: bool
    numeric_conflict: bool
    variant_group: str


def match_product(display_name: str, title: str) -> MatchResult:
    canonical_name = canonicalize_headphone_name(display_name)
    target_tokens = [t for t in tokenize(canonical_name) if len(t) >= 2]
    title_tokens = set(tokenize(title))
    accessory = is_accessory_title(title)
    condition = infer_condition(title)
    variant_group = infer_variant_group(display_name)

    if not target_tokens:
        return MatchResult(canonical_name, display_name, title, 0.0, accessory, False, condition, False, False, variant_group)

    brand = infer_brand(display_name)
    title_norm = normalize_text(title)
    target_norm = normalize_text(display_name)
    brand_conflict = bool(brand) and brand not in title_norm

    numeric_tokens = [t for t in target_tokens if re.search(r"\d", t)]
    numeric_hits = sum(1 for token in numeric_tokens if token in title_tokens)
    numeric_conflict = bool(numeric_tokens) and numeric_hits == 0

    text_hits = sum(1 for token in target_tokens if token in title_tokens)
    base_score = text_hits / max(1, len(target_tokens))
    if numeric_conflict:
        base_score *= 0.2
    elif numeric_tokens:
        base_score *= 1.1

    if brand_conflict:
        base_score *= 0.25

    variant_conflict = False
    for key, pattern in VARIANT_GROUP_PATTERNS.items():
        expected = bool(re.search(pattern, target_norm))
        seen = bool(re.search(pattern, title_norm))
        if expected != seen and (expected or seen):
            variant_conflict = True
            base_score *= 0.7

    if accessory:
        base_score *= 0.15

    return MatchResult(
        canonical_name=canonical_name,
        display_name=display_name,
        title=title,
        match_score=max(0.0, min(1.0, base_score)),
        is_accessory=accessory,
        variant_conflict=variant_conflict,
        condition=condition,
        brand_conflict=brand_conflict,
        numeric_conflict=numeric_conflict,
        variant_group=variant_group,
    )
