"""
JSON message serialization for IPC communication.

This module provides safe JSON-based serialization for inter-process communication,
replacing pickle to avoid security risks when communicating between processes
running at different privilege levels (e.g., admin service and user GUI).
"""

import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def encode_message(message: Dict[str, Any]) -> bytes:
    """
    Encode a message dictionary to JSON bytes.
    
    Args:
        message: Dictionary containing the message data
        
    Returns:
        UTF-8 encoded JSON bytes
        
    Raises:
        TypeError: If message contains non-JSON-serializable types
        ValueError: If message encoding fails
    """
    try:
        json_str = json.dumps(message, ensure_ascii=False)
        return json_str.encode('utf-8')
    except (TypeError, ValueError) as e:
        logger.error(f"Failed to encode message: {e}")
        raise


def decode_message(data: bytes) -> Dict[str, Any]:
    """
    Decode JSON bytes to a message dictionary.
    
    Args:
        data: UTF-8 encoded JSON bytes
        
    Returns:
        Dictionary containing the decoded message
        
    Raises:
        ValueError: If data is not valid JSON
        UnicodeDecodeError: If data is not valid UTF-8
    """
    try:
        json_str = data.decode('utf-8')
        message = json.loads(json_str)
        
        if not isinstance(message, dict):
            raise ValueError(f"Expected dict, got {type(message).__name__}")
            
        return message
    except (ValueError, UnicodeDecodeError) as e:
        logger.error(f"Failed to decode message: {e}")
        raise

