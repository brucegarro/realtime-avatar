"""
Conversation Pipeline - Phase 4
Chains Audio → ASR → LLM → TTS → Video for interactive conversations
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
import time
import asyncio

from models.asr import ASRModel
from models.llm import LLMModel
from pipelines.phase1_script import Phase1Pipeline

logger = logging.getLogger(__name__)


class ConversationPipeline:
    """
    Orchestrates the full conversation pipeline:
    1. Audio Input → ASR (transcription)
    2. Text → LLM (response generation)
    3. Response Text → TTS (voice cloning)
    4. TTS Audio → Video (lip-synced avatar)
    """

    def __init__(
        self,
        reference_image: str,
        reference_audio: str,
        output_dir: str = "outputs/conversations",
        device: str = "cuda",
        use_tensorrt: bool = True,
    ):
        """
        Initialize the conversation pipeline.

        Args:
            reference_image: Path to reference avatar image
            reference_audio: Path to reference voice sample for cloning
            output_dir: Directory to save conversation outputs
            device: Device for inference ('cuda', 'mps', or 'cpu')
            use_tensorrt: Whether to use TensorRT for video generation
        """
        self.reference_image = reference_image
        self.reference_audio = reference_audio
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.device = device
        self.use_tensorrt = use_tensorrt

        # Models (lazy loaded)
        self.asr_model: Optional[ASRModel] = None
        self.llm_model: Optional[LLMModel] = None
        self.phase1_pipeline: Optional[Phase1Pipeline] = None  # For TTS + Video

        # System prompt for conversational LLM
        self.system_prompt = """You are Bruce, a helpful and friendly AI assistant. 
Keep your responses concise (1-3 sentences) and conversational. 
Be natural, warm, and engaging in your communication style."""

        logger.info(f"ConversationPipeline initialized (device={device}, tensorrt={use_tensorrt})")

    def initialize(self):
        """Load all models into memory."""
        start_time = time.time()
        logger.info("Initializing conversation pipeline models...")

        # Initialize ASR
        if self.asr_model is None:
            logger.info("Loading ASR model (Faster-Whisper)...")
            # Use int8 for CPU (float16 requires GPU), float16 for CUDA
            compute_type = "int8" if self.device == "cpu" else "float16"
            self.asr_model = ASRModel(device=self.device, compute_type=compute_type)
            self.asr_model.initialize()

        # Initialize LLM (optional - skip if it fails)
        if self.llm_model is None:
            try:
                logger.info("Loading LLM model (Qwen-2.5-7B)...")
                self.llm_model = LLMModel()  # LLM on CPU (default)
                self.llm_model.initialize()
            except Exception as e:
                logger.warning(f"Failed to load LLM, will use fallback responses: {e}")
                self.llm_model = None  # Will use fallback in generate_response()

        # Note: TTS and Video models are loaded on-demand by phase1_script.run_pipeline()

        elapsed = time.time() - start_time
        logger.info(f"All models initialized in {elapsed:.2f}s")

    def transcribe(self, audio_path: str, language: str = "en") -> Dict[str, Any]:
        """
        Transcribe audio to text using ASR.

        Args:
            audio_path: Path to audio file
            language: Language code (en, zh, es)

        Returns:
            Dict with 'text', 'language', and timing info
        """
        if self.asr_model is None:
            raise RuntimeError("Pipeline not initialized. Call initialize() first.")

        start_time = time.time()
        logger.info(f"Transcribing audio: {audio_path}")

        # ASR model returns (text, language, confidence) tuple
        transcribe_result = self.asr_model.transcribe(audio_path, language=language)
        
        # Handle both tuple formats: (text, language, confidence) or (text, metadata)
        if isinstance(transcribe_result, tuple):
            if len(transcribe_result) == 3:
                # Simple format: (text, language, confidence)
                text, detected_lang, confidence = transcribe_result
                metadata = {
                    "language": detected_lang,
                    "language_probability": confidence
                }
            elif len(transcribe_result) == 2:
                # Detailed format: (text, metadata_dict)
                text, metadata = transcribe_result
            else:
                raise ValueError(f"Unexpected transcribe result format: {len(transcribe_result)} values")
        else:
            raise TypeError(f"Expected tuple from ASR transcribe, got {type(transcribe_result)}")
        
        # Build result dict
        result = {
            "text": text,
            "language": metadata.get("language", language),
            "transcribe_time": time.time() - start_time,
            "metadata": metadata
        }

        logger.info(f"Transcription: '{result['text'][:100]}...' ({result['transcribe_time']:.2f}s)")
        return result

    def generate_response(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        max_tokens: int = 150,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate LLM response to user message.

        Args:
            user_message: User's input text
            conversation_history: Optional list of {'role': 'user'/'assistant', 'content': '...'}
            max_tokens: Maximum response length

        Returns:
            Dict with 'response' text and timing info
        """
        start_time = time.time()
        
        # Fallback if LLM failed to load
        if self.llm_model is None:
            logger.info(f"Using fallback response (LLM not available) for: '{user_message[:100]}...'")
            # Simple echoing fallback - just repeat what user said
            response = user_message
            result = {
                "response": response,
                "llm_time": time.time() - start_time,
                "fallback": True,
            }
            return result

        logger.info(f"Generating LLM response for: '{user_message[:100]}...'")

        prompt_to_use = system_prompt or self.system_prompt
        if conversation_history:
            response = self.llm_model.generate_with_history(
                messages=conversation_history,
                system_prompt=prompt_to_use,
                max_new_tokens=max_tokens,
            )
        else:
            response = self.llm_model.generate_response(
                prompt=user_message,
                system_prompt=prompt_to_use,
                max_new_tokens=max_tokens,
            )

        result = {
            "response": response,
            "llm_time": time.time() - start_time,
        }

        logger.info(f"LLM response: '{response[:100]}...' ({result['llm_time']:.2f}s)")
        return result

    async def generate_avatar_video(
        self,
        text: str,
        output_name: str,
        language: str = "en",
        reference_image: Optional[str] = None,
        voice_sample: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate avatar video from text using TTS + Video pipeline.

        Args:
            text: Text to speak
            output_name: Base name for output files (without extension)
            language: Language code

        Returns:
            Dict with 'video_path', 'audio_path', and timing info
        """
        start_time = time.time()
        logger.info(f"Generating avatar video for: '{text[:100]}...'")

        # Initialize Phase1Pipeline if needed
        if self.phase1_pipeline is None:
            self.phase1_pipeline = Phase1Pipeline()
            self.phase1_pipeline.initialize()

        # Use phase1_script pipeline (TTS + Video) - it's async
        result = await self.phase1_pipeline.generate(
            text=text,
            language=language,
            reference_image=reference_image or self.reference_image,
            voice_sample=voice_sample or self.reference_audio,
            job_id=output_name,
        )

        result["total_generation_time"] = time.time() - start_time
        logger.info(f"Avatar video generated: {result.get('video_path')} ({result['total_generation_time']:.2f}s)")

        return result

    async def process_conversation(
        self,
        audio_path: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        output_name: Optional[str] = None,
        language: str = "en",
        reference_image: Optional[str] = None,
        voice_sample: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Full conversation pipeline: Audio → ASR → LLM → TTS → Video.

        Args:
            audio_path: Path to user's audio input
            conversation_history: Optional conversation context
            output_name: Base name for outputs (auto-generated if None)
            language: Language code

        Returns:
            Dict with all results:
            - transcription: ASR result
            - llm_response: LLM result
            - avatar_video: Video generation result
            - total_time: End-to-end time
        """
        if self.asr_model is None:
            raise RuntimeError("Pipeline not initialized. Call initialize() first.")

        pipeline_start = time.time()
        logger.info(f"Processing conversation from audio: {audio_path}")

        # Step 1: Transcribe user audio
        transcription = self.transcribe(audio_path, language=language)
        user_text = transcription["text"]

        # Step 2: Generate LLM response
        llm_result = self.generate_response(
            user_message=user_text,
            conversation_history=conversation_history,
            system_prompt=system_prompt,
            )
        response_text = llm_result["response"]

        # Step 3: Generate avatar video
        if output_name is None:
            output_name = f"conversation_{int(time.time())}"

        avatar_result = await self.generate_avatar_video(
            text=response_text,
            output_name=output_name,
            language=language,
            reference_image=reference_image,
            voice_sample=voice_sample,
        )

        # Compile results
        total_time = time.time() - pipeline_start
        result = {
            "transcription": transcription,
            "llm_response": llm_result,
            "avatar_video": avatar_result,
            "total_time": total_time,
            "user_text": user_text,
            "response_text": response_text,
        }

        logger.info(f"Conversation processed in {total_time:.2f}s")
        logger.info(f"  User: '{user_text[:80]}...'")
        logger.info(f"  Assistant: '{response_text[:80]}...'")
        logger.info(f"  Video: {avatar_result.get('video_path')}")

        return result
