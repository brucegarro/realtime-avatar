"""
Phase 1 test scenarios: Script-to-video generation
"""
from typing import List, Dict


class Phase1TestScenarios:
    """Test scenarios for Phase 1 pipeline"""
    
    @staticmethod
    def get_scenarios() -> List[Dict]:
        """
        Get Phase 1 test scenarios.
        
        Returns:
            List of test scenario dictionaries
        """
        return [
            {
                'id': 'en_short',
                'name': 'English Short',
                'text': "Hello! I'm Bruce's digital avatar.",
                'language': 'en',
                'reference_image': 'bruce_neutral.jpg',
                'expected_duration_range': (1.0, 3.0)  # seconds
            },
            {
                'id': 'zh_short',
                'name': 'Chinese Short',
                'text': "你好！我是布鲁斯的数字化身。",
                'language': 'zh-cn',
                'reference_image': 'bruce_neutral.jpg',
                'expected_duration_range': (1.0, 3.0)
            },
            {
                'id': 'es_short',
                'name': 'Spanish Short',
                'text': "¡Hola! Soy el avatar digital de Bruce.",
                'language': 'es',
                'reference_image': 'bruce_neutral.jpg',
                'expected_duration_range': (1.0, 3.0)
            },
            # Medium-length tests - Re-enabled with GPU acceleration
            {
                'id': 'en_medium',
                'name': 'English Medium',
                'text': (
                    "Welcome to my digital avatar system. "
                    "I can speak multiple languages and generate realistic video responses. "
                    "This is a demonstration of Phase 1 capabilities."
                ),
                'language': 'en',
                'reference_image': 'bruce_smiling.jpg',
                'expected_duration_range': (5.0, 10.0)
            },
            {
                'id': 'zh_medium',
                'name': 'Chinese Medium',
                'text': (
                    "欢迎来到我的数字化身系统。"
                    "我可以说多种语言并生成逼真的视频响应。"
                    "这是第一阶段能力的演示。"
                ),
                'language': 'zh-cn',
                'reference_image': 'bruce_smiling.jpg',
                'expected_duration_range': (5.0, 10.0)
            },
            {
                'id': 'es_medium',
                'name': 'Spanish Medium',
                'text': (
                    "Bienvenido a mi sistema de avatar digital. "
                    "Puedo hablar varios idiomas y generar respuestas de video realistas. "
                    "Esta es una demostración de las capacidades de la Fase 1."
                ),
                'language': 'es',
                'reference_image': 'bruce_smiling.jpg',
                'expected_duration_range': (5.0, 10.0)
            }
        ]
