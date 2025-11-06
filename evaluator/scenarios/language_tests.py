"""
Language-specific test scenarios
"""
from typing import List, Dict


class LanguageTestScenarios:
    """Test scenarios for multilingual capabilities"""
    
    @staticmethod
    def get_scenarios() -> List[Dict]:
        """
        Get multilingual test scenarios.
        
        Returns:
            List of test scenario dictionaries
        """
        return [
            {
                'id': 'lang_switch_en_zh',
                'name': 'Language Switch: EN → ZH',
                'tests': [
                    {
                        'text': "I can speak English.",
                        'language': 'en',
                        'reference_image': 'bruce_neutral.jpg'
                    },
                    {
                        'text': "我也会说中文。",
                        'language': 'zh-cn',
                        'reference_image': 'bruce_neutral.jpg'
                    }
                ]
            },
            {
                'id': 'lang_switch_en_es',
                'name': 'Language Switch: EN → ES',
                'tests': [
                    {
                        'text': "I can speak English.",
                        'language': 'en',
                        'reference_image': 'bruce_neutral.jpg'
                    },
                    {
                        'text': "También puedo hablar español.",
                        'language': 'es',
                        'reference_image': 'bruce_neutral.jpg'
                    }
                ]
            },
            {
                'id': 'lang_switch_full',
                'name': 'Language Switch: EN → ZH → ES',
                'tests': [
                    {
                        'text': "Hello in English.",
                        'language': 'en',
                        'reference_image': 'bruce_neutral.jpg'
                    },
                    {
                        'text': "你好，这是中文。",
                        'language': 'zh-cn',
                        'reference_image': 'bruce_neutral.jpg'
                    },
                    {
                        'text': "Hola en español.",
                        'language': 'es',
                        'reference_image': 'bruce_neutral.jpg'
                    }
                ]
            }
        ]
