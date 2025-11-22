"""
Streaming Conversation Pipeline
Generates and streams video chunks as they're produced for lower perceived latency.
"""

import logging
import time
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List, AsyncGenerator
import re

from models.asr import ASRModel
from models.llm import LLMModel
from pipelines.phase1_script import Phase1Pipeline

logger = logging.getLogger(__name__)


class StreamingConversationPipeline:
    """
    Streaming conversation pipeline that generates video chunks progressively.
    
    Key improvements over standard pipeline:
    - Splits LLM response into sentence chunks
    - Generates TTS + Avatar for each chunk in parallel
    - Streams video chunks to client as they're ready
    - Reduces time-to-first-frame from ~30s to ~5-6s
    """

    def __init__(
        self,
        reference_image: str,
        reference_audio: str,
        output_dir: str = "outputs/conversations",
        device: str = "cuda",
        use_tensorrt: bool = True,
        max_parallel_chunks: int = 1,  # Must be 1: GPU service processes requests serially
    ):
        """
        Initialize streaming conversation pipeline.

        Args:
            reference_image: Path to reference avatar image
            reference_audio: Path to reference voice sample for cloning
            output_dir: Directory to save conversation outputs
            device: Device for inference ('cuda', 'mps', or 'cpu')
            use_tensorrt: Whether to use TensorRT for video generation
            max_parallel_chunks: Must be 1. GPU service runs single-worker uvicorn and processes
                requests serially. L4 GPU cannot handle concurrent Ditto instances due to CUDA
                context limitations. Parallel requests would just queue at GPU service anyway.
        """
        self.reference_image = reference_image
        self.reference_audio = reference_audio
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.device = device
        self.use_tensorrt = use_tensorrt
        self.max_parallel_chunks = max_parallel_chunks

        # Models (lazy loaded)
        self.asr_model: Optional[ASRModel] = None
        self.llm_model: Optional[LLMModel] = None
        self.phase1_pipeline: Optional[Phase1Pipeline] = None

        # System prompt for conversational LLM
        self.system_prompt = """You are Bruce, a helpful and friendly AI assistant. 
Keep your responses concise (2-4 sentences) and conversational. 
Be natural, warm, and engaging in your communication style."""

        logger.info(f"StreamingConversationPipeline initialized (max_parallel={max_parallel_chunks})")

    def initialize(self):
        """Load all models into memory."""
        start_time = time.time()
        logger.info("Initializing streaming conversation pipeline models...")

        # Initialize ASR
        if self.asr_model is None:
            logger.info("Loading ASR model (Faster-Whisper)...")
            compute_type = "int8" if self.device == "cpu" else "float16"
            self.asr_model = ASRModel(device=self.device, compute_type=compute_type)
            self.asr_model.initialize()

        # Initialize LLM (optional)
        if self.llm_model is None:
            try:
                logger.info("Loading LLM model (Qwen-2.5-7B)...")
                self.llm_model = LLMModel()
                self.llm_model.initialize()
            except Exception as e:
                logger.warning(f"Failed to load LLM, will use fallback: {e}")
                self.llm_model = None

        # Initialize Phase1Pipeline
        if self.phase1_pipeline is None:
            self.phase1_pipeline = Phase1Pipeline()
            self.phase1_pipeline.initialize()

        elapsed = time.time() - start_time
        logger.info(f"Streaming pipeline initialized in {elapsed:.2f}s")

    def split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentence chunks for streaming.
        Handles common abbreviations like D.C., Mr., Dr., etc.
        
        Args:
            text: Text to split
            
        Returns:
            List of sentence strings
        """
        # Handle common abbreviations by temporarily replacing periods
        abbreviations = {
            'D.C.': 'DC_TEMP',
            'Mr.': 'MR_TEMP',
            'Mrs.': 'MRS_TEMP',
            'Ms.': 'MS_TEMP',
            'Dr.': 'DR_TEMP',
            'Jr.': 'JR_TEMP',
            'Sr.': 'SR_TEMP',
            'U.S.': 'US_TEMP',
            'U.K.': 'UK_TEMP',
            'etc.': 'ETC_TEMP',
            'vs.': 'VS_TEMP',
            'e.g.': 'EG_TEMP',
            'i.e.': 'IE_TEMP',
        }
        
        # Replace abbreviations temporarily
        protected_text = text
        replacements = {}
        for abbr, temp in abbreviations.items():
            if abbr in protected_text:
                protected_text = protected_text.replace(abbr, temp)
                replacements[temp] = abbr
        
        # Split on sentence boundaries (.!?) followed by space or end
        sentences = re.split(r'([.!?]+(?:\s+|$))', protected_text)
        
        # Rejoin sentences with their punctuation
        chunks = []
        for i in range(0, len(sentences) - 1, 2):
            sentence = sentences[i].strip()
            punctuation = sentences[i + 1].strip() if i + 1 < len(sentences) else ''
            if sentence:
                chunk = sentence + punctuation
                # Restore abbreviations
                for temp, abbr in replacements.items():
                    chunk = chunk.replace(temp, abbr)
                chunks.append(chunk)
        
        # Handle any remaining text
        if len(sentences) % 2 == 1 and sentences[-1].strip():
            remaining = sentences[-1].strip()
            # Restore abbreviations
            for temp, abbr in replacements.items():
                remaining = remaining.replace(temp, abbr)
            chunks.append(remaining)
        
        # Filter out empty chunks and very short ones (< 3 words)
        chunks = [c for c in chunks if len(c.split()) >= 3]
        
        logger.info(f"Split text into {len(chunks)} chunks: {[c[:40] + '...' for c in chunks]}")
        return chunks

    async def generate_chunk(
        self,
        text_chunk: str,
        chunk_index: int,
        job_id: str,
        language: str = "en",
        reference_image: Optional[str] = None,
        voice_sample: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a single video chunk from text.
        
        Args:
            text_chunk: Text to generate
            chunk_index: Index of this chunk
            job_id: Base job identifier
            language: Language code
            
        Returns:
            Dict with chunk results
        """
        chunk_start = time.time()
        chunk_id = f"{job_id}_chunk{chunk_index}"
        
        logger.info(f"[{chunk_id}] Generating chunk: '{text_chunk[:50]}...'")
        
        try:
            # Generate TTS + Avatar for this chunk
            result = await self.phase1_pipeline.generate(
                text=text_chunk,
                language=language,
                reference_image=reference_image or self.reference_image,
                voice_sample=voice_sample or self.reference_audio,
                job_id=chunk_id,
            )
            
            chunk_time = time.time() - chunk_start
            result["chunk_index"] = chunk_index
            result["chunk_time"] = chunk_time
            result["text_chunk"] = text_chunk
            
            logger.info(f"[{chunk_id}] Chunk generated in {chunk_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"[{chunk_id}] Chunk generation failed: {e}", exc_info=True)
            raise

    async def process_conversation_streaming(
        self,
        audio_path: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        job_id: Optional[str] = None,
        language: str = "en",
        reference_image: Optional[str] = None,
        voice_sample: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream conversation processing with progressive chunk generation.
        
        Args:
            audio_path: Path to user's audio input
            conversation_history: Optional conversation context
            job_id: Base name for outputs (auto-generated if None)
            language: Language code
            
        Yields:
            Dict with chunk results as they're generated:
            - type: "transcription" | "llm_response" | "video_chunk" | "complete"
            - data: Type-specific data
        """
        if self.asr_model is None:
            raise RuntimeError("Pipeline not initialized. Call initialize() first.")

        if job_id is None:
            job_id = f"stream_{int(time.time())}"

        pipeline_start = time.time()
        logger.info(f"[{job_id}] Starting streaming conversation processing")

        try:
            # Step 1: Transcribe user audio
            transcription_start = time.time()
            transcribe_result = self.asr_model.transcribe(audio_path, language=language)
            
            if isinstance(transcribe_result, tuple):
                if len(transcribe_result) == 3:
                    text, detected_lang, confidence = transcribe_result
                    metadata = {"language": detected_lang, "language_probability": confidence}
                else:
                    text, metadata = transcribe_result
            else:
                raise TypeError(f"Unexpected transcribe result type: {type(transcribe_result)}")
            
            transcription_time = time.time() - transcription_start
            user_text = text
            
            # Yield transcription result
            yield {
                "type": "transcription",
                "data": {
                    "text": user_text,
                    "language": metadata.get("language", language),
                    "time": transcription_time,
                }
            }
            
            logger.info(f"[{job_id}] Transcription: '{user_text[:80]}...'")

            # Step 2: Generate LLM response
            llm_start = time.time()
            
            if self.llm_model is None:
                # Fallback: echo user text
                response_text = user_text
                fallback = True
            else:
                if conversation_history:
                    response_text = self.llm_model.generate_with_history(
                        messages=conversation_history,
                        system_prompt=system_prompt or self.system_prompt,
                        max_new_tokens=150,
                    )
                else:
                    response_text = self.llm_model.generate_response(
                        prompt=user_text,
                        system_prompt=system_prompt or self.system_prompt,
                        max_new_tokens=150,
                    )
                fallback = False
            
            llm_time = time.time() - llm_start
            
            # Yield LLM response
            yield {
                "type": "llm_response",
                "data": {
                    "text": response_text,
                    "time": llm_time,
                    "fallback": fallback,
                }
            }
            
            logger.info(f"[{job_id}] LLM response: '{response_text[:80]}...'")

            # Step 3: Split response into chunks and generate video progressively
            chunks = self.split_into_sentences(response_text)
            
            if not chunks:
                # If splitting failed, use full text as single chunk
                chunks = [response_text]
            
            # Generate chunks sequentially and yield as each completes
            # Sequential processing required due to GPU service limitations
            for i, text_chunk in enumerate(chunks):
                # Generate chunk (blocks until complete)
                result = await self.generate_chunk(
                    text_chunk=text_chunk,
                    chunk_index=i,
                    job_id=job_id,
                    language=language,
                    reference_image=reference_image,
                    voice_sample=voice_sample,
                )
                
                # Yield immediately after generation completes
                yield {
                    "type": "video_chunk",
                    "data": result,
                }

            # Yield completion
            total_time = time.time() - pipeline_start
            yield {
                "type": "complete",
                "data": {
                    "total_time": total_time,
                    "num_chunks": len(chunks),
                    "user_text": user_text,
                    "response_text": response_text,
                }
            }
            
            logger.info(f"[{job_id}] Streaming conversation completed in {total_time:.2f}s")

        except Exception as e:
            logger.error(f"[{job_id}] Streaming conversation failed: {e}", exc_info=True)
            yield {
                "type": "error",
                "data": {
                    "error": str(e),
                    "time": time.time() - pipeline_start,
                }
            }
