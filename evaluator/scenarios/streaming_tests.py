"""
Streaming test scenarios for the conversation pipeline.
Tests the /api/v1/conversation/stream endpoint.
"""
import os
from typing import List, Dict, Any

# Base path for fixtures
FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fixtures')


def get_streaming_scenarios() -> List[Dict[str, Any]]:
    """
    Get streaming test scenarios.
    Each scenario tests a specific aspect of the pipeline.
    
    Returns:
        List of test scenario dictionaries
    """
    return [
        # English basic test
        {
            'id': 'stream_en_01',
            'name': 'English Streaming',
            'audio_file': os.path.join(FIXTURES_DIR, 'bruce_en_01.wav'),
            'language': 'en',
            'expected_asr_language': 'en',
            'description': 'Basic English audio through streaming pipeline',
            'validations': ['asr_language', 'has_response', 'has_video']
        },
        
        # Chinese test
        {
            'id': 'stream_zh_01',
            'name': 'Chinese Streaming',
            'audio_file': os.path.join(FIXTURES_DIR, 'bruce_zh_01.wav'),
            'language': 'zh',
            'expected_asr_language': 'zh',
            'description': 'Chinese audio - verify ASR outputs Chinese characters',
            'validations': ['asr_language', 'chinese_script', 'has_response', 'has_video']
        },
        
        # Spanish test
        {
            'id': 'stream_es_01',
            'name': 'Spanish Streaming',
            'audio_file': os.path.join(FIXTURES_DIR, 'bruce_es_01.wav'),
            'language': 'es',
            'expected_asr_language': 'es',
            'description': 'Spanish audio through streaming pipeline',
            'validations': ['asr_language', 'has_response', 'has_video']
        },
        
        # Latency baseline (short clip)
        {
            'id': 'stream_latency_01',
            'name': 'Latency Baseline',
            'audio_file': os.path.join(FIXTURES_DIR, 'bruce_en_short.wav'),
            'language': 'en',
            'expected_asr_language': 'en',
            'description': 'Short English clip for latency baseline',
            'validations': ['ttff_baseline', 'has_video'],
            'ttff_threshold_ms': 15000  # 15 seconds max for first frame
        },
    ]


def get_code_switching_scenarios() -> List[Dict[str, Any]]:
    """
    Get code-switching test scenarios.
    Tests ability to handle mixed-language input.
    
    Note: These require pre-recorded mixed-language audio files.
    """
    return [
        {
            'id': 'stream_codeswitch_zh_01',
            'name': 'Code Switch: Chinese Input',
            'audio_file': os.path.join(FIXTURES_DIR, 'bruce_zh_01.wav'),
            'language': 'zh',
            'expected_asr_language': 'zh',
            'description': 'Chinese input - verify no romanization, proper Chinese output',
            'validations': ['chinese_script', 'no_romanization', 'llm_responds_chinese']
        },
    ]


def validate_scenario_result(scenario: Dict[str, Any], result: Any) -> Dict[str, Any]:
    """
    Validate a scenario result against expected conditions.
    
    Args:
        scenario: Test scenario definition
        result: StreamingResult from the API
        
    Returns:
        Dict with validation results
    """
    validations = scenario.get('validations', [])
    results = {
        'scenario_id': scenario['id'],
        'passed': True,
        'failures': [],
        'details': {}
    }
    
    for validation in validations:
        passed, detail = _run_validation(validation, scenario, result)
        results['details'][validation] = {'passed': passed, 'detail': detail}
        if not passed:
            results['passed'] = False
            results['failures'].append(f"{validation}: {detail}")
    
    return results


def _run_validation(validation: str, scenario: Dict, result: Any) -> tuple:
    """Run a single validation check"""
    
    if validation == 'asr_language':
        expected = scenario.get('expected_asr_language', scenario['language'])
        # Handle language code variations (zh vs zh-cn)
        actual = result.transcription_language
        if expected.startswith('zh') and actual.startswith('zh'):
            return True, f"Language matched: {actual}"
        passed = actual == expected or actual.startswith(expected)
        return passed, f"Expected {expected}, got {actual}"
    
    elif validation == 'has_response':
        has_response = len(result.llm_response_text) > 0
        return has_response, f"Response length: {len(result.llm_response_text)}"
    
    elif validation == 'has_video':
        has_video = result.total_chunks > 0
        return has_video, f"Video chunks: {result.total_chunks}"
    
    elif validation == 'chinese_script':
        # Check if transcription contains Chinese characters (not just pinyin)
        text = result.transcription_text
        has_chinese = any('\u4e00' <= char <= '\u9fff' for char in text)
        return has_chinese, f"Contains Chinese chars: {has_chinese}, text: {text[:50]}"
    
    elif validation == 'no_romanization':
        # Check that Chinese text doesn't have excessive romanization
        text = result.transcription_text.lower()
        # Common pinyin patterns that shouldn't appear in Chinese transcription
        pinyin_markers = ['ni hao', 'wo shi', 'zen me', 'shi de', 'bu shi']
        has_pinyin = any(marker in text for marker in pinyin_markers)
        return not has_pinyin, f"Romanization check: {'FAIL - has pinyin' if has_pinyin else 'PASS'}"
    
    elif validation == 'llm_responds_chinese':
        # Check if LLM response contains Chinese characters
        text = result.llm_response_text
        has_chinese = any('\u4e00' <= char <= '\u9fff' for char in text)
        return has_chinese, f"LLM Chinese response: {has_chinese}"
    
    elif validation == 'ttff_baseline':
        threshold = scenario.get('ttff_threshold_ms', 15000)
        passed = result.ttff_ms <= threshold
        return passed, f"TTFF: {result.ttff_ms:.0f}ms (threshold: {threshold}ms)"
    
    else:
        return True, f"Unknown validation: {validation}"
