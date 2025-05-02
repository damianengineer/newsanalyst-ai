#!/usr/bin/env python3
"""
Claude API Client with 1Password Integration

This module provides a secure and efficient client for interacting with Anthropic's
Claude API, with integrated support for retrieving API keys from 1Password vaults.
"""

import os
import time
import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import subprocess
from typing import Dict, List, Optional, Union, Any, Tuple, Callable
import uuid

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ============================================================================
# CONFIGURATION SETTINGS
# ============================================================================

# 1Password Configuration
OP_VAULT = "demo"          # 1Password vault name
OP_ITEM = "anthropic"      # Item name in the vault
OP_FIELD = "api_key"       # Field name in the item

# Claude API Configuration
CLAUDE_MODEL = "claude-3-7-sonnet-20250219"  # Model to use
API_TIMEOUT = 60         # API request timeout in seconds
MAX_RETRIES = 3          # Maximum number of retries for failed requests
BACKOFF_FACTOR = 0.5     # Backoff factor for retries

# Logging Configuration
LOG_LEVEL = logging.INFO   # Set to logging.DEBUG for more detailed logs
LOG_FILE = "claude_client.log"  # Log file path (set to None to disable file logging)
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Environment Variable Fallback (if 1Password is not available)
ENV_VAR_NAME = "ANTHROPIC_API_KEY"  # Environment variable name for API key

# ============================================================================

# Initialize logger
logger = logging.getLogger("claude_client")


class SecretRetrievalError(Exception):
    """Raised when a secret cannot be retrieved."""


class ClaudeAPIError(Exception):
    """Base exception for Claude API errors."""


@dataclass(frozen=True)
class SecretConfig:
    """Immutable configuration for secret retrieval."""
    vault: str
    item: str
    field: str = "api_key"


def setup_logging(
    level: int = LOG_LEVEL,
    log_file: Optional[Union[str, Path]] = LOG_FILE,
    log_format: str = LOG_FORMAT
) -> None:
    """
    Set up logging configuration.
    
    Args:
        level: Logging level (e.g., logging.INFO, logging.DEBUG).
        log_file: Optional path to log file.
        log_format: Log message format.
    """
    handlers = [logging.StreamHandler()]
    
    if log_file:
        # Ensure directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=handlers
    )
    
    # Set more restrictive log level for noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


class OnePasswordCLIClient:
    """A secure client to interact with 1Password CLI for secret retrieval."""

    def __init__(self, cli_executable: str = "op", timeout: int = 10):
        """
        Initialize the 1Password CLI client.

        Args:
            cli_executable: Path to the 1Password CLI executable.
            timeout: CLI command timeout in seconds.
        """
        self.cli_executable = cli_executable
        self.timeout = timeout
        self._verify_cli_available()
    
    def _verify_cli_available(self) -> None:
        """Verify that the 1Password CLI is available and authenticated."""
        try:
            result = subprocess.run(
                [self.cli_executable, "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout
            )
            if result.returncode != 0:
                logger.warning("1Password CLI may not be properly installed: %s", result.stderr.strip())
            else:
                logger.debug("1Password CLI version: %s", result.stdout.strip())
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.warning("1Password CLI verification failed: %s", e)
    
    @lru_cache(maxsize=32)
    def get_secret(self, config: SecretConfig) -> str:
        """
        Retrieve a secret from a 1Password vault using the CLI.
        
        This method is cached to avoid unnecessary CLI calls for repeated requests
        for the same secret, improving performance.

        Args:
            config: SecretConfig containing vault, item, and field information.

        Returns:
            The secret value as a string.

        Raises:
            SecretRetrievalError: If retrieval fails for any reason.
        """
        command = [
            self.cli_executable, "item", "get", config.item,
            "--vault", config.vault,
            "--fields", config.field,
            "--format", "json"
        ]

        try:
            logger.debug("Executing 1Password CLI command to retrieve secret")
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                timeout=self.timeout
            )

            # Parse JSON output
            output: Union[Dict, List[Dict]] = json.loads(result.stdout)
            
            # Handle both single object and list cases
            if isinstance(output, dict):
                if output.get("label") == config.field:
                    secret = output.get("value")
                    if secret:
                        return secret
                    raise SecretRetrievalError(f"Empty value for field '{config.field}'")
                raise SecretRetrievalError(f"Field '{config.field}' not found in output")
            
            elif isinstance(output, list):
                for field_data in output:
                    if field_data.get("label") == config.field:
                        secret = field_data.get("value")
                        if secret:
                            return secret
                        raise SecretRetrievalError(f"Empty value for field '{config.field}'")
                raise SecretRetrievalError(f"Field '{config.field}' not found in output")
            
            else:
                raise SecretRetrievalError(f"Unexpected output type: {type(output)}")

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else "Unknown error"
            raise SecretRetrievalError(f"1Password CLI command failed: {error_msg}") from e
        except subprocess.TimeoutExpired as e:
            raise SecretRetrievalError(f"1Password CLI command timed out after {self.timeout}s") from e
        except json.JSONDecodeError as e:
            raise SecretRetrievalError(f"Failed to parse 1Password CLI output: {e}") from e
        except Exception as e:
            raise SecretRetrievalError(f"Unexpected error retrieving secret: {e}") from e


class ClaudeClient:
    """A robust client for interacting with Claude API chat completions endpoint."""
    
    # Constants
    BASE_URL = "https://api.anthropic.com/v1/messages"
    DEFAULT_MODEL = CLAUDE_MODEL
    API_VERSION = "2023-06-01"
    DEFAULT_TIMEOUT = API_TIMEOUT
    DEFAULT_USER_ID = "user-" + str(uuid.uuid4())  # Generate a unique user ID
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        op_config: Optional[SecretConfig] = None,
        env_var_name: str = ENV_VAR_NAME,
        request_timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        retry_backoff_factor: float = BACKOFF_FACTOR,
        session: Optional[requests.Session] = None,
    ):
        """
        Initialize the Claude client with secure authentication options.
        
        Args:
            api_key: Direct API key (least recommended for production).
            op_config: 1Password configuration for API key retrieval.
            env_var_name: Environment variable name for API key fallback.
            request_timeout: Timeout for API requests in seconds.
            max_retries: Maximum number of retries for failed requests.
            retry_backoff_factor: Backoff factor for retries.
            session: Optional pre-configured requests session.
        
        Raises:
            ValueError: If no authentication method succeeds.
        """
        self.request_id_generator = self._create_request_id_generator()
        self.request_timeout = request_timeout
        self.session = session or self._create_session(max_retries, retry_backoff_factor)
        
        # Get API key with priority order
        self.api_key = self._get_api_key(api_key, op_config, env_var_name)
        
        # Prepare headers (without API key - will be added per request)
        self.common_headers = {
            "anthropic-version": self.API_VERSION,
            "content-type": "application/json",
        }
        
    def _create_session(self, max_retries: int, retry_backoff_factor: float) -> requests.Session:
        """Create and configure a requests session with retry logic."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=retry_backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        return session
    
    def _create_request_id_generator(self) -> Callable[[], str]:
        """Create a generator function for unique request IDs."""
        def generate_request_id() -> str:
            """Generate a unique request ID for tracing."""
            return str(uuid.uuid4())
        return generate_request_id
    
    def _get_api_key(
        self, 
        api_key: Optional[str], 
        op_config: Optional[SecretConfig],
        env_var_name: str
    ) -> str:
        """
        Get API key from available sources with proper priority.
        
        Args:
            api_key: Direct API key.
            op_config: 1Password configuration.
            env_var_name: Environment variable name.
            
        Returns:
            API key as string.
            
        Raises:
            ValueError: If no API key can be retrieved.
        """
        # Try direct API key first
        if api_key:
            logger.debug("Using directly provided API key")
            return api_key
        
        # Try 1Password integration
        if op_config:
            try:
                logger.info("Attempting to retrieve API key from 1Password...")
                op_client = OnePasswordCLIClient()
                key = op_client.get_secret(op_config)
                logger.info("Successfully retrieved API key from 1Password")
                return key
            except SecretRetrievalError as e:
                logger.warning("Failed to retrieve API key from 1Password: %s", e)
        
        # Try environment variable
        env_key = os.environ.get(env_var_name)
        if env_key:
            logger.info("Using API key from environment variable %s", env_var_name)
            return env_key
        
        # No API key available
        raise ValueError(
            f"No API key available. Provide directly, set environment variable {env_var_name}, "
            "or configure 1Password access."
        )
    
    def chat_completion(
        self, 
        messages: List[Dict[str, str]],
        model: str = DEFAULT_MODEL,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        system: Optional[str] = None,
        stream: bool = False,
        user_id: Optional[str] = None,
        stop_sequences: Optional[List[str]] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Send a request to Claude's chat completion endpoint with comprehensive error handling.
        
        Args:
            messages: List of message objects with role and content keys.
            model: Claude model to use.
            max_tokens: Maximum number of tokens to generate.
            temperature: Sampling temperature (0-1).
            system: Optional system prompt to set context.
            stream: Whether to stream the response.
            user_id: Optional user identifier for API telemetry.
            stop_sequences: Optional custom text sequences that cause the model to stop.
            top_p: Optional nucleus sampling parameter (0-1).
            top_k: Optional parameter to limit tokens considered for each step.
            
        Returns:
            The API response as a dictionary.
            
        Raises:
            ClaudeAPIError: If the API request fails.
        """
        # Generate unique request ID for tracing
        request_id = self.request_id_generator()
        
        # Prepare headers with request-specific values
        headers = {
            **self.common_headers,
            "x-api-key": self.api_key,
            "x-request-id": request_id
        }
        
        # Prepare payload
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        
        # Add optional parameters if provided
        if system:
            payload["system"] = system
            
        if user_id:
            # Add user_id as a metadata field using standard format
            payload["metadata"] = {"user_id": user_id}
        else:
            # Use default user ID for tracking
            payload["metadata"] = {"user_id": self.DEFAULT_USER_ID}
            
        if stop_sequences:
            payload["stop_sequences"] = stop_sequences
            
        if top_p is not None:
            payload["top_p"] = top_p
            
        if top_k is not None:
            payload["top_k"] = top_k
        
        # Log request info (without sensitive data)
        logger.info(
            "Sending request to Claude API - model: %s, max_tokens: %d, request_id: %s",
            model, max_tokens, request_id
        )
        
        start_time = time.time()
        
        try:
            response = self.session.post(
                self.BASE_URL,
                headers=headers,
                json=payload,
                timeout=self.request_timeout
            )
            
            elapsed_time = time.time() - start_time
            logger.info(
                "Received response in %.2fs - status: %d, request_id: %s",
                elapsed_time, response.status_code, request_id
            )
            
            # Handle HTTP errors
            response.raise_for_status()
            
            # Parse response
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            # Try to extract API error message
            error_detail = "Unknown error"
            try:
                error_json = e.response.json()
                error_detail = error_json.get("error", {}).get("message", "Unknown error")
            except (ValueError, AttributeError):
                if e.response and e.response.text:
                    error_detail = e.response.text[:100]
            
            elapsed_time = time.time() - start_time
            logger.error(
                "HTTP error in Claude API request - status: %d, error: %s, request_id: %s, elapsed: %.2fs",
                e.response.status_code, error_detail, request_id, elapsed_time
            )
            
            raise ClaudeAPIError(f"Claude API HTTP error: {error_detail}") from e
            
        except requests.exceptions.Timeout:
            elapsed_time = time.time() - start_time
            logger.error(
                "Timeout error in Claude API request - request_id: %s, elapsed: %.2fs",
                request_id, elapsed_time
            )
            raise ClaudeAPIError(f"Claude API request timed out after {self.request_timeout}s") from None
            
        except requests.exceptions.RequestException as e:
            elapsed_time = time.time() - start_time
            logger.error(
                "Network error in Claude API request - error: %s, request_id: %s, elapsed: %.2fs",
                str(e), request_id, elapsed_time
            )
            raise ClaudeAPIError(f"Claude API request failed: {e}") from e
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(
                "Unexpected error in Claude API request - error: %s, request_id: %s, elapsed: %.2fs",
                str(e), request_id, elapsed_time
            )
            raise ClaudeAPIError(f"Unexpected error in Claude API request: {e}") from e


def process_claude_response(response: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Process Claude API response, handling various response formats.
    
    Args:
        response: The API response dictionary.
        
    Returns:
        Tuple of (success, content).
    """
    if not response:
        return False, "Empty response received"
    
    # Check for error in response
    if "error" in response:
        error_msg = response.get("error", {}).get("message", "Unknown error")
        return False, f"API error: {error_msg}"
    
    # Extract content blocks
    if "content" in response:
        result = []
        for block in response["content"]:
            if block.get("type") == "text":
                result.append(block.get("text", ""))
        
        if result:
            return True, "\n".join(result)
        return False, "No text content found in response"
    
    return False, f"Unexpected response format: {list(response.keys())}"


def main() -> None:
    """Main function demonstrating the Claude client with 1Password integration."""
    # Set up logging
    setup_logging(
        level=LOG_LEVEL,
        log_file=LOG_FILE,
        log_format=LOG_FORMAT
    )
    
    try:
        # 1Password vault configuration from global settings
        op_config = SecretConfig(
            vault=OP_VAULT,
            item=OP_ITEM, 
            field=OP_FIELD
        )
        
        # Initialize client with 1Password integration
        client = ClaudeClient(
            op_config=op_config,
            env_var_name=ENV_VAR_NAME,
            request_timeout=API_TIMEOUT,
            max_retries=MAX_RETRIES,
            retry_backoff_factor=BACKOFF_FACTOR
        )
        
        # Example system prompt
        system_prompt = (
            "You are Claude, an AI assistant created by Anthropic. "
            "Be helpful, harmless, and honest."
        )
        
        # Example message history
        messages = [
            {"role": "user", "content": "Hello, can you explain what makes Claude unique?"}
        ]
        
        # Make request using configuration from globals
        logger.info("Sending request to Claude API...")
        response = client.chat_completion(
            messages=messages,
            system=system_prompt,
            max_tokens=500,
            temperature=0.7,
            model=CLAUDE_MODEL
        )
        
        # Process response
        success, content = process_claude_response(response)
        
        if success:
            logger.info("Successfully received response from Claude")
            print("\nClaude's response:")
            print(content)
        else:
            logger.error("Failed to get valid response: %s", content)
            print(f"Error: {content}")
            
    except (ClaudeAPIError, SecretRetrievalError, ValueError) as e:
        logger.exception("Error in Claude client: %s", e)
        print(f"An error occurred: {e}")
        
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        print("\nProcess interrupted")
        
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
    