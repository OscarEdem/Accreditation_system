import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class TranslationService:
    _translations = {}
    _initialized = False

    def __init__(self):
        if not TranslationService._initialized:
            self._load_translations()
            TranslationService._initialized = True

    def _load_translations(self):
        """Loads all .json language files from the locales directory."""
        # Navigate from app/services up to the app/ directory
        app_dir = Path(__file__).resolve().parent.parent
        locales_dir = app_dir / "locales"
        
        if not locales_dir.is_dir():
            logger.warning(f"Locales directory not found at {locales_dir}. No translations will be loaded.")
            return

        for lang_file in locales_dir.glob("*.json"):
            lang_code = lang_file.stem
            try:
                with open(lang_file, "r", encoding="utf-8") as f:
                    TranslationService._translations[lang_code] = json.load(f)
                logger.info(f"Successfully loaded translation file: {lang_file.name}")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load or parse translation file {lang_file.name}: {e}")

    def get_string(self, key: str, lang: str = "en", **kwargs) -> str:
        """
        Gets a translated string by key and language, formatting it with provided context.
        Falls back to English if the language or key is not found.
        """
        lang_dict = TranslationService._translations.get(lang, TranslationService._translations.get("en"))

        if not lang_dict:
            logger.error(f"No translations found for language '{lang}' and no fallback to 'en' is available.")
            return key

        template = lang_dict.get(key, TranslationService._translations.get("en", {}).get(key))

        if template is None:
            logger.warning(f"Translation key '{key}' not found in '{lang}' or fallback 'en'.")
            return key

        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing context variable '{e}' for translation key '{key}' in lang '{lang}'.")
            return template