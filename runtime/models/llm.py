"""
LLM (Large Language Model) wrapper
Using Qwen-2.5 for conversational responses
"""
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class LLMModel:
    """
    LLM wrapper for generating conversational responses.
    Uses Qwen-2.5 (7B locally, 14B-INT4 on GPU).
    
    Note: This is a stub for Phase 2/3 implementation.
    """
    
    def __init__(self, model_name: str = "Qwen/Qwen2.5-7B-Instruct"):
        """
        Initialize LLM.
        
        Args:
            model_name: HuggingFace model name
        """
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        self._initialized = False
        
    def initialize(self):
        """Load Qwen model"""
        if self._initialized:
            return
            
        logger.info(f"Loading LLM: {self.model_name}...")
        
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True
            )
            
            # Load model (quantized for efficiency)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto",
                trust_remote_code=True
            )
            
            self._initialized = True
            logger.info(f"LLM loaded: {self.model_name}")
            
        except Exception as e:
            logger.error(f"Failed to load LLM: {e}")
            raise
    
    def is_ready(self) -> bool:
        """Check if model is initialized"""
        return self._initialized and self.model is not None
    
    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 256,
        temperature: float = 0.7,
        language: str = "en"
    ) -> str:
        """
        Generate conversational response.
        
        Args:
            prompt: User input
            system_prompt: System instructions
            max_tokens: Maximum response length
            temperature: Sampling temperature
            language: Response language hint
            
        Returns:
            Generated response text
        """
        if not self.is_ready():
            self.initialize()
        
        try:
            # Format messages
            messages = []
            
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            # Apply chat template
            text = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            
            # Tokenize
            inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)
            
            # Generate
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=True,
                top_p=0.95
            )
            
            # Decode
            response = self.tokenizer.decode(
                outputs[0][len(inputs[0]):],
                skip_special_tokens=True
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            raise
    
    def generate_with_history(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 256,
        temperature: float = 0.7
    ) -> str:
        """
        Generate response with conversation history.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum response length
            temperature: Sampling temperature
            
        Returns:
            Generated response text
        """
        if not self.is_ready():
            self.initialize()
        
        try:
            # Apply chat template
            text = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            
            # Tokenize
            inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)
            
            # Generate
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=True,
                top_p=0.95
            )
            
            # Decode
            response = self.tokenizer.decode(
                outputs[0][len(inputs[0]):],
                skip_special_tokens=True
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"Response generation with history failed: {e}")
            raise
    
    def cleanup(self):
        """Cleanup model resources"""
        if self.model:
            del self.model
            del self.tokenizer
            self._initialized = False
            logger.info("LLM cleaned up")


# Global instance
_llm_model: Optional[LLMModel] = None


def get_llm_model() -> LLMModel:
    """Get or create global LLM instance"""
    global _llm_model
    if _llm_model is None:
        _llm_model = LLMModel()
    return _llm_model
