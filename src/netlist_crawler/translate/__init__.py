"""Public netlist dialect translation API."""

from .consistency import ConsistencyResult, normalize_spice, verify_spectre_spice
from .core import (
    TranslationError,
    TranslationIssue,
    TranslationResult,
    convert_file,
    convert_text,
)
from .profiles import TranslationProfile, get_profile

__all__ = [
    "ConsistencyResult",
    "TranslationError",
    "TranslationIssue",
    "TranslationProfile",
    "TranslationResult",
    "convert_file",
    "convert_text",
    "get_profile",
    "normalize_spice",
    "verify_spectre_spice",
]
