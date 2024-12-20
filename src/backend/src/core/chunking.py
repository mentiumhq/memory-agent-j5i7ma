"""
Core module for intelligent document chunking and token management.

This module provides enterprise-grade document chunking capabilities with:
- Model-specific token limits and validation
- Semantic boundary detection
- Configurable chunk overlap
- Token counting with caching
- Comprehensive chunk metadata

Version: 1.0.0
"""

from functools import lru_cache
from typing import List, Dict, Optional, Iterator, Tuple
import tiktoken  # version: 0.5.1
import logging
from .errors import DocumentError, ErrorCode

# Constants for token management
DEFAULT_CHUNK_SIZE = 4000
GPT35_MAX_TOKENS = 16384
GPT4_MAX_TOKENS = 32768
OVERLAP_SIZE = 200

# Supported models with their token limits
SUPPORTED_MODELS = {
    'gpt-3.5-turbo': GPT35_MAX_TOKENS,
    'gpt-4': GPT4_MAX_TOKENS
}

# Semantic boundary patterns in descending priority
SEMANTIC_BOUNDARIES = [
    '.\n\n',  # Paragraph breaks
    '\n\n',   # Double line breaks
    '.\n',    # Sentence with line break
    '.',      # Sentence end
    '\n',     # Single line break
    ';',      # Semicolon
    ':',      # Colon
    '!',      # Exclamation
    '?'       # Question
]

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1000)
def count_tokens(text: str, model_name: str = 'gpt-3.5-turbo') -> int:
    """
    Count tokens in text using model-specific tokenizer with caching.
    
    Args:
        text: Input text to count tokens for
        model_name: Name of the model to use for tokenization
        
    Returns:
        Number of tokens in the text
        
    Raises:
        DocumentError: If tokenization fails or model is not supported
    """
    if model_name not in SUPPORTED_MODELS:
        raise DocumentError(
            f"Unsupported model: {model_name}",
            ErrorCode.VALIDATION_ERROR,
            {'supported_models': list(SUPPORTED_MODELS.keys())}
        )
    
    try:
        encoding = tiktoken.encoding_for_model(model_name)
        return len(encoding.encode(text))
    except Exception as e:
        logger.error(f"Token counting failed: {str(e)}")
        raise DocumentError(
            "Failed to count tokens",
            ErrorCode.DOCUMENT_NOT_FOUND,
            {'error': str(e)}
        )

def split_text(text: str, 
               chunk_size: Optional[int] = None,
               model_name: Optional[str] = 'gpt-3.5-turbo') -> List[Dict[str, any]]:
    """
    Split text into chunks respecting semantic boundaries and token limits.
    
    Args:
        text: Input text to split
        chunk_size: Maximum tokens per chunk (defaults to model-specific)
        model_name: Model name for token counting
        
    Returns:
        List of chunks with metadata including token count and overlap info
    """
    if not text:
        return []
        
    # Validate and set chunk size
    max_tokens = SUPPORTED_MODELS.get(model_name, GPT35_MAX_TOKENS)
    if not chunk_size:
        chunk_size = DEFAULT_CHUNK_SIZE
    elif chunk_size > max_tokens:
        chunk_size = max_tokens
        
    chunks = []
    current_chunk = ""
    current_tokens = 0
    
    # Split text into initial chunks
    for paragraph in text.split('\n\n'):
        paragraph_tokens = count_tokens(paragraph, model_name)
        
        if current_tokens + paragraph_tokens > chunk_size:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = paragraph
                current_tokens = paragraph_tokens
            else:
                # Handle paragraphs larger than chunk_size
                chunks.extend(_split_large_paragraph(paragraph, chunk_size, model_name))
        else:
            current_chunk = current_chunk + '\n\n' + paragraph if current_chunk else paragraph
            current_tokens += paragraph_tokens
            
    if current_chunk:
        chunks.append(current_chunk)
        
    # Process chunks with overlap and metadata
    return _process_chunks(chunks, chunk_size, model_name)

def merge_chunks(chunks: List[Dict[str, any]], 
                max_tokens: Optional[int] = None) -> List[Dict[str, any]]:
    """
    Intelligently merge small chunks while preserving semantic meaning.
    
    Args:
        chunks: List of chunk dictionaries
        max_tokens: Maximum tokens for merged chunks
        
    Returns:
        Optimized list of merged chunks
    """
    if not chunks:
        return []
        
    if not max_tokens:
        max_tokens = DEFAULT_CHUNK_SIZE
        
    merged = []
    current_chunk = None
    
    for chunk in chunks:
        if not current_chunk:
            current_chunk = chunk
            continue
            
        # Check if chunks can be merged
        combined_tokens = current_chunk['tokens'] + chunk['tokens']
        if combined_tokens <= max_tokens:
            # Merge chunks
            current_chunk['content'] += f"\n\n{chunk['content']}"
            current_chunk['tokens'] = combined_tokens
            current_chunk['merged'] = True
        else:
            merged.append(current_chunk)
            current_chunk = chunk
            
    if current_chunk:
        merged.append(current_chunk)
        
    # Update sequence numbers
    for i, chunk in enumerate(merged):
        chunk['sequence'] = i + 1
        
    return merged

class DocumentChunker:
    """
    Manages document chunking with model-specific strategies and caching.
    """
    
    def __init__(self, 
                 model_name: Optional[str] = 'gpt-3.5-turbo',
                 chunk_size: Optional[int] = None):
        """
        Initialize chunker with model configuration and caching.
        
        Args:
            model_name: Name of the LLM model to use
            chunk_size: Maximum tokens per chunk
        """
        if model_name not in SUPPORTED_MODELS:
            raise DocumentError(
                f"Unsupported model: {model_name}",
                ErrorCode.VALIDATION_ERROR,
                {'supported_models': list(SUPPORTED_MODELS.keys())}
            )
            
        self._model_name = model_name
        self._chunk_size = chunk_size or DEFAULT_CHUNK_SIZE
        self._tokenizer = tiktoken.encoding_for_model(model_name)
        self._cache = {}
        
    def chunk_document(self, text: str) -> List[Dict[str, any]]:
        """
        Split document into optimized chunks with metadata.
        
        Args:
            text: Document text to chunk
            
        Returns:
            List of chunks with metadata
            
        Raises:
            DocumentError: If chunking fails
        """
        # Check cache
        cache_key = hash(text)
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        try:
            # Generate initial chunks
            chunks = split_text(text, self._chunk_size, self._model_name)
            
            # Optimize chunks
            if len(chunks) > 1:
                chunks = merge_chunks(chunks, self._chunk_size)
                
            # Cache results
            self._cache[cache_key] = chunks
            return chunks
            
        except Exception as e:
            logger.error(f"Document chunking failed: {str(e)}")
            raise DocumentError(
                "Failed to chunk document",
                ErrorCode.DOCUMENT_NOT_FOUND,
                {'error': str(e)}
            )
            
    def get_token_count(self, text: str) -> int:
        """
        Get cached token count for text.
        
        Args:
            text: Input text
            
        Returns:
            Number of tokens
        """
        return count_tokens(text, self._model_name)

def _split_large_paragraph(paragraph: str, 
                          chunk_size: int,
                          model_name: str) -> List[str]:
    """
    Split large paragraphs at semantic boundaries.
    
    Args:
        paragraph: Large paragraph to split
        chunk_size: Maximum chunk size
        model_name: Model name for token counting
        
    Returns:
        List of smaller paragraph chunks
    """
    chunks = []
    current_chunk = ""
    current_tokens = 0
    
    # Try each boundary type in order
    for boundary in SEMANTIC_BOUNDARIES:
        sentences = paragraph.split(boundary)
        
        for sentence in sentences:
            if not sentence:
                continue
                
            sentence_tokens = count_tokens(sentence, model_name)
            
            if current_tokens + sentence_tokens > chunk_size:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
                current_tokens = sentence_tokens
            else:
                current_chunk = current_chunk + boundary + sentence if current_chunk else sentence
                current_tokens += sentence_tokens
                
    if current_chunk:
        chunks.append(current_chunk)
        
    return chunks

def _process_chunks(chunks: List[str],
                   chunk_size: int,
                   model_name: str) -> List[Dict[str, any]]:
    """
    Add overlap and metadata to chunks.
    
    Args:
        chunks: List of text chunks
        chunk_size: Maximum chunk size
        model_name: Model name for token counting
        
    Returns:
        Processed chunks with metadata
    """
    processed_chunks = []
    
    for i, chunk in enumerate(chunks):
        # Add overlap with previous chunk
        overlap_start = ""
        if i > 0:
            prev_chunk = chunks[i-1]
            overlap_start = _get_overlap_text(prev_chunk, OVERLAP_SIZE, model_name)
            
        # Add overlap with next chunk
        overlap_end = ""
        if i < len(chunks) - 1:
            next_chunk = chunks[i+1]
            overlap_end = _get_overlap_text(next_chunk, OVERLAP_SIZE, model_name, start=True)
            
        # Combine text with overlaps
        full_text = f"{overlap_start}{chunk}{overlap_end}".strip()
        
        # Create chunk metadata
        processed_chunks.append({
            'content': full_text,
            'sequence': i + 1,
            'tokens': count_tokens(full_text, model_name),
            'overlap_tokens': count_tokens(overlap_start + overlap_end, model_name),
            'has_previous': bool(overlap_start),
            'has_next': bool(overlap_end)
        })
        
    return processed_chunks

def _get_overlap_text(text: str,
                     overlap_tokens: int,
                     model_name: str,
                     start: bool = False) -> str:
    """
    Extract overlap text from chunk.
    
    Args:
        text: Source text for overlap
        overlap_tokens: Number of tokens to overlap
        model_name: Model name for token counting
        start: Whether to take from start (True) or end (False)
        
    Returns:
        Overlap text
    """
    tokens = text.split()
    if not tokens:
        return ""
        
    overlap_text = ""
    current_tokens = 0
    
    if start:
        tokens = tokens[:overlap_tokens]
    else:
        tokens = tokens[-overlap_tokens:]
        
    for token in tokens:
        token_count = count_tokens(token, model_name)
        if current_tokens + token_count > overlap_tokens:
            break
        overlap_text += f" {token}"
        current_tokens += token_count
        
    return overlap_text.strip()