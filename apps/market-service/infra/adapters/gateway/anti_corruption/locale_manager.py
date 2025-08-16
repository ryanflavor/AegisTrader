"""
Locale Manager for vnpy Chinese encoding requirements.

IMPORTANT: vnpy CTP/SOPT requires Chinese locale to function correctly.
This module centralizes locale management to ensure proper encoding.
"""

import locale
import logging
import os
import warnings
from typing import ClassVar

logger = logging.getLogger(__name__)


class LocaleManager:
    """Manages Chinese locale setup required by vnpy CTP/SOPT."""

    _initialized: ClassVar[bool] = False
    _original_locale: ClassVar[tuple[str, str] | None] = None

    @classmethod
    def setup_chinese_locale(cls) -> bool:
        """
        Setup Chinese locale required by vnpy.

        Returns:
            True if setup successful, False otherwise
        """
        if cls._initialized:
            return True

        # Skip on Windows (different locale handling)
        if os.name == "nt":
            cls._initialized = True
            return True

        # Save original locale for restoration
        try:
            cls._original_locale = locale.getlocale()
        except Exception:
            pass

        # Try different Chinese locale variants
        locale_variants = [
            "zh_CN.gb18030",
            "zh_CN.GB18030",
            "zh_CN.GBK",
            "zh_CN.UTF-8",
        ]

        for locale_name in locale_variants:
            try:
                os.environ["LC_ALL"] = locale_name
                os.environ["LANG"] = locale_name
                locale.setlocale(locale.LC_ALL, locale_name)
                logger.info(f"Successfully set Chinese locale: {locale_name}")
                cls._initialized = True
                return True
            except locale.Error:
                continue

        # Warn if no Chinese locale available
        warnings.warn(
            "Chinese locale not available. vnpy CTP/SOPT may not work properly.\n"
            "Install with: sudo locale-gen zh_CN.GB18030 && sudo update-locale\n"
            "This is a requirement from vnpy framework for CTP/SOPT connectivity.",
            RuntimeWarning,
        )
        return False

    @classmethod
    def restore_locale(cls) -> None:
        """Restore original locale if possible."""
        if cls._original_locale:
            try:
                locale.setlocale(locale.LC_ALL, cls._original_locale)
                logger.info(f"Restored original locale: {cls._original_locale}")
            except Exception as e:
                logger.warning(f"Failed to restore locale: {e}")

    @classmethod
    def ensure_initialized(cls) -> None:
        """Ensure locale is initialized before vnpy operations."""
        if not cls._initialized:
            cls.setup_chinese_locale()
