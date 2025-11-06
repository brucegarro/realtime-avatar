"""
Language detection and processing utilities
"""
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


# Language code mappings
LANGUAGE_CODES = {
    'en': 'English',
    'zh': 'Chinese',
    'zh-cn': 'Chinese (Mandarin)',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'ja': 'Japanese',
    'ko': 'Korean',
    'ar': 'Arabic',
    'ru': 'Russian'
}

# XTTS-v2 supported languages
XTTS_LANGUAGES = [
    'en', 'es', 'fr', 'de', 'it', 'pt', 'pl', 'tr',
    'ru', 'nl', 'cs', 'ar', 'zh-cn', 'ja', 'hu', 'ko'
]


def detect_language(text: str) -> str:
    """
    Detect language from text.
    
    Args:
        text: Input text
        
    Returns:
        Language code (en, zh-cn, es, etc.)
    """
    try:
        from langdetect import detect, LangDetectException
        
        detected = detect(text)
        
        # Map common codes
        lang_map = {
            'zh-cn': 'zh-cn',
            'zh-tw': 'zh-cn',
            'zh': 'zh-cn'
        }
        
        return lang_map.get(detected, detected)
        
    except Exception as e:
        logger.warning(f"Language detection failed: {e}")
        return 'en'  # Default to English


def is_supported_language(language: str) -> bool:
    """
    Check if language is supported by XTTS-v2.
    
    Args:
        language: Language code
        
    Returns:
        True if supported
    """
    return language in XTTS_LANGUAGES


def get_language_name(language_code: str) -> str:
    """
    Get full language name from code.
    
    Args:
        language_code: Language code
        
    Returns:
        Full language name
    """
    return LANGUAGE_CODES.get(language_code, language_code)


def normalize_language_code(language: str) -> str:
    """
    Normalize language code to XTTS-v2 format.
    
    Args:
        language: Input language code
        
    Returns:
        Normalized language code
    """
    lang_lower = language.lower().strip()
    
    # Normalize variations
    normalizations = {
        'zh': 'zh-cn',
        'chinese': 'zh-cn',
        'mandarin': 'zh-cn',
        'english': 'en',
        'spanish': 'es',
        'french': 'fr',
        'german': 'de',
        'japanese': 'ja',
        'korean': 'ko'
    }
    
    return normalizations.get(lang_lower, lang_lower)


def split_multilingual_text(text: str) -> List[dict]:
    """
    Split text by language segments.
    Useful for handling mixed-language input.
    
    Args:
        text: Input text (may contain multiple languages)
        
    Returns:
        List of dicts with 'text' and 'language' keys
    """
    # Simple implementation: detect language for entire text
    # TODO: Implement proper language segmentation
    language = detect_language(text)
    
    return [{'text': text, 'language': language}]


def get_voice_sample_for_language(
    language: str,
    voice_samples_dir: str
) -> Optional[str]:
    """
    Get appropriate voice sample for language.
    
    Args:
        language: Language code
        voice_samples_dir: Directory containing voice samples
        
    Returns:
        Path to voice sample or None
    """
    import os
    
    # Try to find language-specific sample
    base_lang = language.split('-')[0]  # Get base (e.g., 'zh' from 'zh-cn')
    
    possible_files = [
        f"bruce_{language}_sample.wav",
        f"bruce_{base_lang}_sample.wav",
        f"bruce_en_sample.wav"  # Fallback to English
    ]
    
    for filename in possible_files:
        path = os.path.join(voice_samples_dir, filename)
        if os.path.exists(path):
            logger.debug(f"Found voice sample: {filename}")
            return path
    
    logger.warning(f"No voice sample found for language: {language}")
    return None


def translate_text(
    text: str,
    source_lang: str,
    target_lang: str
) -> str:
    """
    Translate text from source to target language.
    
    Note: This is a stub. Would require translation API (Google, DeepL, etc.)
    
    Args:
        text: Input text
        source_lang: Source language code
        target_lang: Target language code
        
    Returns:
        Translated text
    """
    logger.warning("Translation not implemented - returning original text")
    return text


def estimate_speaking_duration(text: str, language: str = 'en') -> float:
    """
    Estimate how long it will take to speak text.
    
    Args:
        text: Input text
        language: Language code
        
    Returns:
        Estimated duration in seconds
    """
    # Rough estimates: words per minute by language
    wpm = {
        'en': 150,
        'zh-cn': 200,  # Characters per minute
        'es': 160,
        'fr': 140,
        'de': 130
    }
    
    rate = wpm.get(language, 150)
    
    if language.startswith('zh'):
        # Chinese: count characters
        char_count = len(text)
        return (char_count / rate) * 60
    else:
        # Other languages: count words
        word_count = len(text.split())
        return (word_count / rate) * 60
