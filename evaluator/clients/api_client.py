"""
API client for streaming conversation endpoint.
Parses SSE events and extracts server-reported timings.
"""
import asyncio
import httpx
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class StreamingResult:
    """Result from streaming conversation endpoint"""
    # Request info
    request_start_time: float = 0.0
    
    # Transcription
    transcription_text: str = ""
    transcription_language: str = ""
    transcription_time_ms: float = 0.0
    
    # LLM Response
    llm_response_text: str = ""
    llm_time_ms: float = 0.0
    
    # Video chunks
    video_chunks: List[Dict[str, Any]] = field(default_factory=list)
    ttff_ms: float = 0.0  # Time to first frame (first video_chunk event)
    total_chunks: int = 0
    
    # Overall timing
    total_pipeline_ms: float = 0.0
    complete_time: float = 0.0
    
    # Video paths for analysis
    video_paths: List[str] = field(default_factory=list)
    
    # Errors
    error: Optional[str] = None
    success: bool = False


class StreamingAPIClient:
    """Client for the streaming conversation API"""
    
    def __init__(self, base_url: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
    async def check_health(self) -> bool:
        """Check if the API is healthy"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{self.base_url}/health")
                health = response.json()
                return health.get('status') in ['healthy', 'initializing']
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return False
    
    async def stream_conversation(
        self,
        audio_path: str,
        language: str = "en",
        conversation_history: Optional[List[Dict]] = None
    ) -> StreamingResult:
        """
        Send audio to streaming conversation endpoint and parse SSE response.
        
        Args:
            audio_path: Path to audio file (wav format)
            language: Language code (en, zh, es)
            conversation_history: Optional conversation context
            
        Returns:
            StreamingResult with all timing metrics and outputs
        """
        result = StreamingResult()
        result.request_start_time = time.time()
        
        try:
            # Prepare multipart form data
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
            
            files = {'audio': ('audio.wav', audio_data, 'audio/wav')}
            data = {'language': language}
            if conversation_history:
                data['conversation_history'] = json.dumps(conversation_history)
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    'POST',
                    f"{self.base_url}/api/v1/conversation/stream",
                    files=files,
                    data=data
                ) as response:
                    if response.status_code != 200:
                        result.error = f"HTTP {response.status_code}"
                        return result
                    
                    # Parse SSE events
                    buffer = ""
                    first_video_time = None
                    
                    async for chunk in response.aiter_text():
                        buffer += chunk
                        
                        # Process complete events (double newline separated)
                        while '\n\n' in buffer:
                            event_str, buffer = buffer.split('\n\n', 1)
                            event = self._parse_sse_event(event_str)
                            
                            if event:
                                self._process_event(event, result, first_video_time)
                                
                                # Track time to first video
                                if event.get('type') == 'video_chunk' and first_video_time is None:
                                    first_video_time = time.time()
                                    result.ttff_ms = (first_video_time - result.request_start_time) * 1000
            
            result.complete_time = time.time()
            result.total_pipeline_ms = (result.complete_time - result.request_start_time) * 1000
            result.success = True
            
        except Exception as e:
            result.error = str(e)
            logger.error(f"Stream conversation failed: {e}")
        
        return result
    
    def _parse_sse_event(self, event_str: str) -> Optional[Dict]:
        """Parse SSE event string into dict"""
        event_type = None
        event_data = None
        
        for line in event_str.strip().split('\n'):
            if line.startswith('event:'):
                event_type = line[6:].strip()
            elif line.startswith('data:'):
                try:
                    event_data = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
        
        if event_type and event_data:
            return {'type': event_type, 'data': event_data}
        return None
    
    def _process_event(self, event: Dict, result: StreamingResult, first_video_time: Optional[float]):
        """Process a single SSE event and update result"""
        event_type = event.get('type')
        data = event.get('data', {})
        
        if event_type == 'transcription':
            result.transcription_text = data.get('text', '')
            result.transcription_language = data.get('language', '')
            result.transcription_time_ms = data.get('time', 0) * 1000  # Convert to ms
            
        elif event_type == 'llm_response':
            result.llm_response_text = data.get('text', '')
            result.llm_time_ms = data.get('time', 0) * 1000 if 'time' in data else 0
            
        elif event_type == 'video_chunk':
            chunk_info = {
                'chunk_index': data.get('chunk_index', len(result.video_chunks)),
                'chunk_time_ms': data.get('chunk_time', 0) * 1000,
                'video_path': data.get('video_path', ''),
            }
            result.video_chunks.append(chunk_info)
            result.total_chunks = len(result.video_chunks)
            
            if data.get('video_path'):
                result.video_paths.append(data['video_path'])
                
        elif event_type == 'complete':
            # Final event
            pass
        
        elif event_type == 'error':
            result.error = data.get('message', 'Unknown error')
    
    async def download_video(self, video_filename: str, output_path: str) -> bool:
        """Download a video file from the API"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}/api/v1/videos/{video_filename}")
                if response.status_code == 200:
                    with open(output_path, 'wb') as f:
                        f.write(response.content)
                    return True
        except Exception as e:
            logger.error(f"Failed to download video: {e}")
        return False
