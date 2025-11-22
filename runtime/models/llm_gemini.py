"""
Gemini LLM Client for Conversational Responses
Uses Google Cloud Vertex AI Gemini 2.0 Flash API
"""
import logging
from typing import Optional, List, Dict
import google.generativeai as genai
from vertexai.preview.generative_models import GenerativeModel, ChatSession
import vertexai

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Gemini API client for generating conversational responses.
    Drop-in replacement for local LLMModel using Vertex AI.
    """
    
    def __init__(
        self,
        model_name: str = "gemini-2.0-flash-exp",
        project_id: str = "realtime-avatar-bg",
        location: str = "us-central1"
    ):
        """
        Initialize Gemini client.
        
        Args:
            model_name: Gemini model name (gemini-2.0-flash-exp, gemini-1.5-flash, etc.)
            project_id: GCP project ID
            location: GCP region for Vertex AI
        """
        self.model_name = model_name
        self.project_id = project_id
        self.location = location
        self.model = None
        self.chat_session: Optional[ChatSession] = None
        self._initialized = False
        
        # System prompt for concise conversational responses
        self.system_instruction = """You are Bruce, a helpful and friendly AI assistant.
Keep your responses concise (2-4 sentences) and conversational.
Be natural, warm, and engaging in your communication style.
Avoid long explanations unless specifically asked."""
        
    def initialize(self):
        """Initialize Vertex AI and Gemini model"""
        if self._initialized:
            return
            
        logger.info(f"Initializing Gemini client: {self.model_name}")
        
        try:
            # Initialize Vertex AI
            vertexai.init(project=self.project_id, location=self.location)
            
            # Create generative model with system instruction
            self.model = GenerativeModel(
                self.model_name,
                system_instruction=[self.system_instruction]
            )
            
            self._initialized = True
            logger.info(f"Gemini client initialized: {self.model_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise
    
    def is_ready(self) -> bool:
        """Check if client is initialized"""
        return self._initialized
    
    def generate_response(
        self,
        prompt: str,
        max_tokens: int = 150,
        temperature: float = 0.7
    ) -> str:
        """
        Generate a single response to a prompt.
        
        Args:
            prompt: User input text
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0-1.0)
            
        Returns:
            Generated response text
        """
        if not self.is_ready():
            self.initialize()
        
        try:
            logger.info(f"Generating Gemini response for: '{prompt[:50]}...'")
            
            # Configure generation parameters
            generation_config = {
                "max_output_tokens": max_tokens,
                "temperature": temperature,
                "top_p": 0.95,
            }
            
            # Generate response
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            response_text = response.text.strip()
            logger.info(f"Gemini response generated: {len(response_text)} chars")
            
            return response_text
            
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            # Fallback response
            return f"I heard you say: {prompt}"
    
    def generate_with_history(
        self,
        prompt: str,
        conversation_history: List[Dict[str, str]],
        max_tokens: int = 150,
        temperature: float = 0.7
    ) -> str:
        """
        Generate response with conversation history context.
        
        Args:
            prompt: Current user input
            conversation_history: List of {"role": "user"|"assistant", "content": str}
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            
        Returns:
            Generated response text
        """
        if not self.is_ready():
            self.initialize()
        
        try:
            logger.info(f"Generating Gemini response with history ({len(conversation_history)} turns)")
            
            # Start or continue chat session
            if self.chat_session is None:
                self.chat_session = self.model.start_chat()
            
            # Build conversation history if this is a new session
            if len(conversation_history) > 0:
                # Gemini tracks history automatically in chat sessions
                # For now, just include the most recent context in the prompt
                recent_context = conversation_history[-2:] if len(conversation_history) >= 2 else conversation_history
                context_text = "\n".join([
                    f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
                    for msg in recent_context
                ])
                full_prompt = f"Previous context:\n{context_text}\n\nUser: {prompt}"
            else:
                full_prompt = prompt
            
            # Configure generation
            generation_config = {
                "max_output_tokens": max_tokens,
                "temperature": temperature,
                "top_p": 0.95,
            }
            
            # Send message to chat
            response = self.chat_session.send_message(
                full_prompt,
                generation_config=generation_config
            )
            
            response_text = response.text.strip()
            logger.info(f"Gemini response generated: {len(response_text)} chars")
            
            return response_text
            
        except Exception as e:
            logger.error(f"Gemini generation with history failed: {e}")
            # Fallback
            return f"I heard you say: {prompt}"
    
    def reset_chat(self):
        """Reset the chat session"""
        self.chat_session = None
        logger.info("Gemini chat session reset")
    
    def cleanup(self):
        """Cleanup resources"""
        self.chat_session = None
        self._initialized = False
        logger.info("Gemini client cleaned up")


# Global instance
_gemini_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """Get or create global Gemini client instance"""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client
