"""
Quick streaming eval runner.
Runs ~6 tests against the streaming conversation endpoint.
Target runtime: <3 minutes.

Usage:
    python run_streaming_eval.py --url http://34.74.34.221:8000
    
    # Or use environment variable
    RUNTIME_URL=http://34.74.34.221:8000 python run_streaming_eval.py
"""
import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from clients.api_client import StreamingAPIClient, StreamingResult
from scenarios.streaming_tests import (
    get_streaming_scenarios,
    get_code_switching_scenarios,
    validate_scenario_result
)
from metrics.streaming import calculate_streaming_metrics, compare_to_baseline
from metrics.tts_accuracy import calculate_tts_accuracy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASELINES_DIR = os.path.join(os.path.dirname(__file__), 'baselines')
OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), 'outputs')
BASELINE_FILE = os.path.join(BASELINES_DIR, 'streaming_baseline.json')


class StreamingEvaluator:
    """Evaluator for streaming conversation pipeline"""
    
    def __init__(self, runtime_url: str, output_dir: str = OUTPUTS_DIR):
        self.client = StreamingAPIClient(runtime_url)
        self.output_dir = output_dir
        self.results: List[Dict[str, Any]] = []
        self.baseline = self._load_baseline()
        
        os.makedirs(output_dir, exist_ok=True)
    
    def _load_baseline(self) -> Dict:
        """Load baseline metrics for comparison"""
        if os.path.exists(BASELINE_FILE):
            with open(BASELINE_FILE, 'r') as f:
                return json.load(f)
        return {"scenarios": {}}
    
    def _save_baseline(self, results: List[Dict]):
        """Save current results as new baseline"""
        baseline = {
            "created_at": datetime.utcnow().isoformat() + "Z",
            "description": "Auto-generated baseline",
            "scenarios": {}
        }
        
        for result in results:
            if result.get('success'):
                baseline["scenarios"][result['scenario_id']] = result.get('metrics', {})
        
        with open(BASELINE_FILE, 'w') as f:
            json.dump(baseline, f, indent=2)
        
        logger.info(f"Saved baseline to {BASELINE_FILE}")
    
    async def run_scenario(self, scenario: Dict) -> Dict[str, Any]:
        """Run a single test scenario"""
        scenario_id = scenario['id']
        logger.info(f"Running scenario: {scenario_id} - {scenario['name']}")
        
        start_time = time.time()
        
        # Check audio file exists
        audio_file = scenario['audio_file']
        if not os.path.exists(audio_file):
            return {
                'scenario_id': scenario_id,
                'success': False,
                'error': f"Audio file not found: {audio_file}"
            }
        
        # Run the streaming request
        result = await self.client.stream_conversation(
            audio_path=audio_file,
            language=scenario['language']
        )
        
        elapsed = time.time() - start_time
        
        # Build result dict
        scenario_result = {
            'scenario_id': scenario_id,
            'scenario_name': scenario['name'],
            'success': result.success,
            'elapsed_s': elapsed,
            'error': result.error
        }
        
        if result.success:
            # Calculate metrics
            metrics = calculate_streaming_metrics(result)
            scenario_result['metrics'] = metrics
            
            # Run validations
            validation_result = validate_scenario_result(scenario, result)
            scenario_result['validations'] = validation_result
            scenario_result['all_validations_passed'] = validation_result['passed']
            
            # Compare to baseline if available
            baseline_metrics = self.baseline.get('scenarios', {}).get(scenario_id)
            if baseline_metrics:
                comparison = compare_to_baseline(metrics, baseline_metrics)
                scenario_result['baseline_comparison'] = comparison
            
            # Store raw result data for debugging
            scenario_result['transcription'] = result.transcription_text
            scenario_result['llm_response'] = result.llm_response_text[:200] + "..." if len(result.llm_response_text) > 200 else result.llm_response_text
        
        return scenario_result
    
    async def run_all(self, include_code_switching: bool = True) -> Dict[str, Any]:
        """Run all test scenarios"""
        logger.info("Starting streaming eval suite")
        suite_start = time.time()
        
        # Check API health first
        if not await self.client.check_health():
            return {
                'success': False,
                'error': 'API health check failed',
                'results': []
            }
        
        # Gather scenarios
        scenarios = get_streaming_scenarios()
        if include_code_switching:
            scenarios.extend(get_code_switching_scenarios())
        
        logger.info(f"Running {len(scenarios)} scenarios")
        
        # Run scenarios sequentially (to avoid overwhelming the GPU)
        results = []
        for scenario in scenarios:
            result = await self.run_scenario(scenario)
            results.append(result)
            self.results.append(result)
            
            # Log progress
            status = "✓" if result.get('success') and result.get('all_validations_passed', True) else "✗"
            logger.info(f"  {status} {scenario['id']}: {result.get('elapsed_s', 0):.1f}s")
        
        suite_elapsed = time.time() - suite_start
        
        # Calculate summary
        passed = sum(1 for r in results if r.get('success') and r.get('all_validations_passed', True))
        failed = len(results) - passed
        
        summary = {
            'success': failed == 0,
            'total_scenarios': len(results),
            'passed': passed,
            'failed': failed,
            'suite_time_s': suite_elapsed,
            'results': results,
            'has_regressions': any(
                r.get('baseline_comparison', {}).get('has_regressions', False) 
                for r in results
            )
        }
        
        return summary
    
    def print_report(self, summary: Dict):
        """Print a human-readable report"""
        print("\n" + "="*60)
        print("STREAMING EVAL REPORT")
        print("="*60)
        
        # Overall status
        status = "PASS ✓" if summary['success'] else "FAIL ✗"
        print(f"\nOverall: {status}")
        print(f"Scenarios: {summary['passed']}/{summary['total_scenarios']} passed")
        print(f"Suite time: {summary['suite_time_s']:.1f}s")
        
        if summary.get('has_regressions'):
            print("\n⚠️  REGRESSIONS DETECTED")
        
        # Individual results
        print("\n" + "-"*60)
        print("SCENARIO RESULTS")
        print("-"*60)
        
        for result in summary['results']:
            scenario_id = result['scenario_id']
            
            if result.get('success') and result.get('all_validations_passed', True):
                status_icon = "✓"
            else:
                status_icon = "✗"
            
            print(f"\n{status_icon} {scenario_id}")
            
            if result.get('error'):
                print(f"  Error: {result['error']}")
                continue
            
            # Metrics
            metrics = result.get('metrics', {})
            print(f"  ASR: {metrics.get('asr_time_ms', 0):.0f}ms | "
                  f"LLM: {metrics.get('llm_time_ms', 0):.0f}ms | "
                  f"TTFF: {metrics.get('ttff_ms', 0):.0f}ms | "
                  f"Total: {metrics.get('total_pipeline_ms', 0):.0f}ms")
            
            # Transcription preview
            if result.get('transcription'):
                preview = result['transcription'][:60] + "..." if len(result['transcription']) > 60 else result['transcription']
                print(f"  Transcription: {preview}")
            
            # Validation failures
            validations = result.get('validations', {})
            if validations.get('failures'):
                print(f"  ⚠️  Validation failures: {validations['failures']}")
            
            # Regressions
            comparison = result.get('baseline_comparison', {})
            if comparison.get('regressions'):
                print(f"  ⚠️  Regressions: {[r['metric'] for r in comparison['regressions']]}")
        
        print("\n" + "="*60)
    
    def save_results(self, summary: Dict, update_baseline: bool = False):
        """Save results to JSON file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(self.output_dir, f'streaming_eval_{timestamp}.json')
        
        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        logger.info(f"Results saved to {output_file}")
        
        if update_baseline:
            self._save_baseline(summary['results'])


async def main():
    parser = argparse.ArgumentParser(description='Run streaming pipeline evaluation')
    parser.add_argument('--url', type=str, 
                        default=os.getenv('RUNTIME_URL', 'http://localhost:8000'),
                        help='Runtime API URL')
    parser.add_argument('--update-baseline', action='store_true',
                        help='Update baseline with current results')
    parser.add_argument('--no-code-switching', action='store_true',
                        help='Skip code-switching tests')
    parser.add_argument('--output-dir', type=str, default=OUTPUTS_DIR,
                        help='Directory for output files')
    
    args = parser.parse_args()
    
    logger.info(f"Runtime URL: {args.url}")
    
    evaluator = StreamingEvaluator(args.url, args.output_dir)
    
    summary = await evaluator.run_all(
        include_code_switching=not args.no_code_switching
    )
    
    evaluator.print_report(summary)
    evaluator.save_results(summary, update_baseline=args.update_baseline)
    
    # Exit with appropriate code
    sys.exit(0 if summary['success'] else 1)


if __name__ == '__main__':
    asyncio.run(main())
