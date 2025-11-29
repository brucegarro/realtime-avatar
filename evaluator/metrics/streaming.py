"""
Streaming latency metrics - extracted from SSE events.
"""
from typing import Dict, Any
from dataclasses import asdict

# Import will be from api_client when used
# from clients.api_client import StreamingResult


def calculate_streaming_metrics(result: Any) -> Dict[str, Any]:
    """
    Calculate streaming latency metrics from a StreamingResult.
    
    Args:
        result: StreamingResult from api_client
        
    Returns:
        Dict with timing metrics
    """
    metrics = {
        # ASR timing
        "asr_time_ms": result.transcription_time_ms,
        "asr_language": result.transcription_language,
        
        # LLM timing
        "llm_time_ms": result.llm_time_ms,
        
        # Video generation
        "ttff_ms": result.ttff_ms,  # Time to first frame
        "total_chunks": result.total_chunks,
        "chunk_times_ms": [c.get('chunk_time_ms', 0) for c in result.video_chunks],
        
        # Overall pipeline
        "total_pipeline_ms": result.total_pipeline_ms,
        
        # Derived metrics
        "video_generation_ms": sum(c.get('chunk_time_ms', 0) for c in result.video_chunks),
    }
    
    # Calculate average chunk time
    if result.video_chunks:
        metrics["avg_chunk_time_ms"] = metrics["video_generation_ms"] / len(result.video_chunks)
    else:
        metrics["avg_chunk_time_ms"] = 0
    
    return metrics


def compare_to_baseline(
    current: Dict[str, Any],
    baseline: Dict[str, Any],
    thresholds: Dict[str, float] = None
) -> Dict[str, Any]:
    """
    Compare current metrics to baseline and flag regressions.
    
    Args:
        current: Current run metrics
        baseline: Baseline metrics to compare against
        thresholds: Dict of metric_name -> max_regression_pct (default 20%)
        
    Returns:
        Dict with comparison results and regression flags
    """
    if thresholds is None:
        thresholds = {
            "asr_time_ms": 0.20,
            "llm_time_ms": 0.20,
            "ttff_ms": 0.30,
            "total_pipeline_ms": 0.20,
            "video_generation_ms": 0.20,
        }
    
    comparison = {
        "regressions": [],
        "improvements": [],
        "details": {}
    }
    
    for metric, threshold in thresholds.items():
        if metric not in current or metric not in baseline:
            continue
            
        current_val = current[metric]
        baseline_val = baseline[metric]
        
        if baseline_val == 0:
            continue
            
        pct_change = (current_val - baseline_val) / baseline_val
        
        comparison["details"][metric] = {
            "current": current_val,
            "baseline": baseline_val,
            "pct_change": pct_change,
            "threshold": threshold
        }
        
        if pct_change > threshold:
            comparison["regressions"].append({
                "metric": metric,
                "current": current_val,
                "baseline": baseline_val,
                "pct_change": pct_change
            })
        elif pct_change < -threshold:
            comparison["improvements"].append({
                "metric": metric,
                "current": current_val,
                "baseline": baseline_val,
                "pct_change": pct_change
            })
    
    comparison["has_regressions"] = len(comparison["regressions"]) > 0
    
    return comparison
