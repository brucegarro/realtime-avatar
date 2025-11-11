"""
Streaming pipeline for real-time avatar conversation
Connects ASR → LLM → TTS → Video in a parallel streaming architecture
"""
import asyncio
import logging
import time
from typing import Optional, AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path
import tempfile

logger = logging.getLogger(__name__)


@dataclass
class StreamingConfig:
    """Configuration for streaming pipeline"""
    # ASR settings
    asr_model_size: str = "base"
    asr_language: Optional[str] = None  # None = auto-detect
    use_vad: bool = True
    
    # LLM settings
    llm_model: str = "gpt-3.5-turbo"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 150
    
    # TTS settings
    tts_backend: str = "styletts2"  # "styletts2" or "xtts"
    voice_reference: Optional[str] = None
    tts_speed: float = 1.0
    
    # Video settings
    video_backend: str = "ditto"  # "ditto" or "liveportrait"
    reference_image: Optional[str] = None
    video_resolution: tuple = (512, 512)
    
    # Streaming settings
    sentence_chunk_size: int = 1  # Process after N sentences
    audio_chunk_duration: float = 2.0  # seconds
    max_queue_size: int = 10
    

class StreamingPipeline:
    """
    Real-time streaming pipeline for avatar conversations.
    
    Architecture:
        User Speech → ASR → LLM → TTS → Video → Output Stream
                       ↓      ↓     ↓      ↓
                   [Queue] [Queue] [Queue] [Queue]
    
    Each stage processes chunks in parallel for minimal latency.
    """
    
    def __init__(self, config: StreamingConfig):
        self.config = config
        self._initialized = False
        
        # Models (lazy-loaded)
        self.asr_model = None
        self.llm_client = None
        self.tts_model = None
        self.video_model = None
        
        # Queues for inter-stage communication
        self.asr_queue = asyncio.Queue(maxsize=config.max_queue_size)
        self.llm_queue = asyncio.Queue(maxsize=config.max_queue_size)
        self.tts_queue = asyncio.Queue(maxsize=config.max_queue_size)
        self.video_queue = asyncio.Queue(maxsize=config.max_queue_size)
        
    async def initialize(self):
        """Initialize all pipeline components"""
        if self._initialized:
            return
        
        logger.info("Initializing streaming pipeline...")
        start_time = time.time()
        
        try:
            # Initialize ASR
            from models.asr import ASRModel
            self.asr_model = ASRModel(device="cuda")
            await asyncio.to_thread(
                self.asr_model.initialize,
                model_size=self.config.asr_model_size,
                use_vad=self.config.use_vad
            )
            
            # Initialize TTS
            if self.config.tts_backend == "styletts2":
                from models.styletts2_model import StyleTTS2Model
                self.tts_model = StyleTTS2Model(device="cuda")
                await asyncio.to_thread(self.tts_model.initialize)
            else:
                from models.tts import TTSModel
                self.tts_model = TTSModel(device="cuda")
                await asyncio.to_thread(self.tts_model.initialize)
            
            # Initialize Video
            if self.config.video_backend == "ditto":
                from models.ditto_model import DittoModel
                self.video_model = DittoModel(device="cuda")
                await asyncio.to_thread(self.video_model.initialize)
            else:
                from models.avatar import AvatarModel
                self.video_model = AvatarModel(device="cuda")
                await asyncio.to_thread(self.video_model.initialize)
            
            # Initialize LLM client (OpenAI or other)
            self._initialize_llm()
            
            self._initialized = True
            elapsed = time.time() - start_time
            logger.info(f"Pipeline initialized in {elapsed:.2f}s")
            
        except Exception as e:
            logger.error(f"Pipeline initialization failed: {e}")
            raise
    
    def _initialize_llm(self):
        """Initialize LLM client"""
        try:
            import openai
            self.llm_client = openai.AsyncOpenAI()
            logger.info(f"LLM client initialized ({self.config.llm_model})")
        except Exception as e:
            logger.warning(f"LLM client init failed: {e}")
            self.llm_client = None
    
    async def process_conversation(
        self,
        audio_input: str,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[list] = None
    ) -> AsyncIterator[dict]:
        """
        Process a full conversation turn: speech → text → response → audio → video.
        
        Args:
            audio_input: Path to input audio file
            system_prompt: System prompt for LLM
            conversation_history: Previous conversation messages
            
        Yields:
            Progress updates and final video chunks
        """
        if not self._initialized:
            raise RuntimeError("Pipeline not initialized. Call initialize() first.")
        
        logger.info("Processing conversation turn...")
        start_time = time.time()
        
        try:
            # Stage 1: Speech-to-Text
            yield {"stage": "asr", "status": "started"}
            
            transcription, asr_meta = await asyncio.to_thread(
                self.asr_model.transcribe,
                audio_input,
                language=self.config.asr_language
            )
            
            yield {
                "stage": "asr",
                "status": "complete",
                "text": transcription,
                "language": asr_meta["language"],
                "duration": time.time() - start_time
            }
            
            # Stage 2: LLM Response (streaming)
            yield {"stage": "llm", "status": "started"}
            
            async for text_chunk in self._stream_llm_response(
                transcription, system_prompt, conversation_history
            ):
                yield {
                    "stage": "llm",
                    "status": "streaming",
                    "text": text_chunk
                }
                
                # Stage 3: TTS (parallel processing)
                await self.tts_queue.put(text_chunk)
            
            yield {"stage": "llm", "status": "complete"}
            
            # Stage 4: Generate video chunks
            yield {"stage": "video", "status": "started"}
            
            async for video_chunk in self._generate_video_stream():
                yield {
                    "stage": "video",
                    "status": "streaming",
                    "video_path": video_chunk,
                    "duration": time.time() - start_time
                }
            
            yield {
                "stage": "complete",
                "total_duration": time.time() - start_time
            }
            
        except Exception as e:
            logger.error(f"Conversation processing failed: {e}")
            yield {"stage": "error", "error": str(e)}
            raise
    
    async def _stream_llm_response(
        self,
        user_text: str,
        system_prompt: Optional[str],
        conversation_history: Optional[list]
    ) -> AsyncIterator[str]:
        """Stream LLM response sentence by sentence"""
        if not self.llm_client:
            # Fallback: echo user text
            yield f"Echo: {user_text}"
            return
        
        try:
            # Build messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if conversation_history:
                messages.extend(conversation_history)
            messages.append({"role": "user", "content": user_text})
            
            # Stream response
            response = await self.llm_client.chat.completions.create(
                model=self.config.llm_model,
                messages=messages,
                temperature=self.config.llm_temperature,
                max_tokens=self.config.llm_max_tokens,
                stream=True
            )
            
            current_sentence = []
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    current_sentence.append(text)
                    
                    # Yield complete sentences
                    full_text = "".join(current_sentence)
                    if any(p in text for p in ['.', '!', '?', '\n']):
                        yield full_text.strip()
                        current_sentence = []
            
            # Yield remaining text
            if current_sentence:
                yield "".join(current_sentence).strip()
                
        except Exception as e:
            logger.error(f"LLM streaming failed: {e}")
            yield f"[LLM Error: {str(e)}]"
    
    async def _generate_video_stream(self) -> AsyncIterator[str]:
        """Generate video chunks from TTS audio queue"""
        try:
            while not self.tts_queue.empty() or self.tts_queue._unfinished_tasks > 0:
                # Get text chunk from queue
                text_chunk = await asyncio.wait_for(
                    self.tts_queue.get(),
                    timeout=5.0
                )
                
                # Generate audio
                audio_path = await asyncio.to_thread(
                    self._synthesize_audio,
                    text_chunk
                )
                
                # Generate video
                video_path = await asyncio.to_thread(
                    self._generate_video_chunk,
                    audio_path
                )
                
                yield video_path
                
                self.tts_queue.task_done()
                
        except asyncio.TimeoutError:
            logger.warning("TTS queue timeout")
        except Exception as e:
            logger.error(f"Video generation failed: {e}")
            raise
    
    def _synthesize_audio(self, text: str) -> str:
        """Synthesize audio from text"""
        output_path = tempfile.mktemp(suffix=".wav")
        
        if hasattr(self.tts_model, 'synthesize'):
            # StyleTTS2 or custom TTS
            self.tts_model.synthesize(
                text=text,
                reference_audio=self.config.voice_reference,
                output_path=output_path
            )
        else:
            # XTTS fallback
            self.tts_model.generate(
                text=text,
                output_path=output_path,
                speaker_wav=self.config.voice_reference
            )
        
        return output_path
    
    def _generate_video_chunk(self, audio_path: str) -> str:
        """Generate video from audio chunk"""
        output_path = tempfile.mktemp(suffix=".mp4")
        
        self.video_model.generate_video(
            audio_path=audio_path,
            reference_image_path=self.config.reference_image,
            output_path=output_path
        )
        
        return output_path
    
    async def process_realtime_stream(
        self,
        audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[dict]:
        """
        Process real-time audio stream (future implementation).
        
        Args:
            audio_stream: Async iterator yielding audio bytes
            
        Yields:
            Real-time video frames
        """
        raise NotImplementedError("Real-time streaming coming in Phase 3")
