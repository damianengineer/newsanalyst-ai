#!/usr/bin/env python3
"""
Claude API Client Module

A simplified version of the claude.py example script, providing a client for
interacting with Anthropic's Claude API with 1Password integration.
"""

import os
import json
import logging
import uuid
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Union, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logger = logging.getLogger(__name__)

# Default configuration
CLAUDE_MODEL = "claude-3-7-sonnet-20250219"  # Default model to use
API_TIMEOUT = 300  # API request timeout in seconds (5 minutes)
MAX_RETRIES = 3  # Maximum number of retries for failed requests
BACKOFF_FACTOR = 0.5  # Backoff factor for retries
ENV_VAR_NAME = "ANTHROPIC_API_KEY"  # Environment variable name for API key


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
    """Client for interacting with Claude API."""
    
    def __init__(
        self,
        op_config: Optional[SecretConfig] = None,
        env_var_name: str = ENV_VAR_NAME,
        api_base: str = "https://api.anthropic.com",
        request_timeout: int = API_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        retry_backoff_factor: float = BACKOFF_FACTOR,
        session: Optional[requests.Session] = None,
    ):
        """
        Initialize the Claude client.
        
        Args:
            op_config: 1Password configuration for retrieving the API key
            env_var_name: Name of the environment variable containing the API key
            api_base: Base URL for the Claude API
            request_timeout: Timeout for API requests in seconds
            max_retries: Maximum number of retries for failed requests
            retry_backoff_factor: Backoff factor for retries
            session: Optional pre-configured requests session
        """
        self.api_base = api_base
        self.api_key = self._get_api_key(op_config, env_var_name)
        self.request_timeout = request_timeout
        
        if not self.api_key:
            raise ValueError(
                "Claude API key not found. Please set it in the environment variable "
                f"'{env_var_name}' or configure 1Password access."
            )
        
        self.session = session or self._create_session(max_retries, retry_backoff_factor)
    
    def _create_session(self, max_retries: int, retry_backoff_factor: float) -> requests.Session:
        """Create and configure a requests session with retry logic."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=retry_backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        return session

    def _get_api_key(
        self, 
        op_config: Optional[SecretConfig], 
        env_var_name: str
    ) -> Optional[str]:
        """
        Get the API key from 1Password or environment variable.
        
        Args:
            op_config: 1Password configuration
            env_var_name: Name of the environment variable
            
        Returns:
            API key if found, None otherwise
        """
        # Try to get API key from 1Password if configured
        if op_config:
            try:
                logger.info(f"Attempting to retrieve API key from 1Password item '{op_config.item}'")
                op_client = OnePasswordCLIClient()
                return op_client.get_secret(op_config)
            except SecretRetrievalError as e:
                logger.warning(f"Failed to retrieve API key from 1Password: {e}")
        
        # Fall back to environment variable
        api_key = os.environ.get(env_var_name)
        if api_key:
            logger.info(f"Using API key from environment variable {env_var_name}")
            return api_key
        
        logger.warning(f"API key not found in environment variable {env_var_name}")
        return None
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = CLAUDE_MODEL,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        system: Optional[str] = None,
        stream: bool = False,
        request_timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a chat completion with Claude.
        
        Args:
            messages: List of message objects with role and content
            model: Claude model to use
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature (0-1)
            system: System prompt
            stream: Whether to stream the response
            request_timeout: Timeout for the API request in seconds, defaults to the client's timeout
            
        Returns:
            API response as a dictionary
        """
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        if system:
            payload["system"] = system
            
        logger.debug(f"Sending request to Claude API with model {model}")
        
        # Use the instance timeout if no specific timeout is provided
        timeout = request_timeout if request_timeout is not None else self.request_timeout
        
        try:
            response = self.session.post(
                f"{self.api_base}/v1/messages",
                headers=headers,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Claude API: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            raise
    
    def get_completion(
        self,
        prompt: str,
        model: str = CLAUDE_MODEL,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        system: Optional[str] = None,
        request_timeout: Optional[int] = None
    ) -> str:
        """
        Get a completion from Claude.
        
        Args:
            prompt: User prompt
            model: Claude model to use
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature (0-1)
            system: System prompt
            request_timeout: Timeout for the API request in seconds, defaults to the client's timeout
            
        Returns:
            Generated text as a string
        """
        messages = [{"role": "user", "content": prompt}]
        response = self.chat_completion(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            request_timeout=request_timeout
        )
        
        return response.get("content", [{}])[0].get("text", "")


def process_claude_response(response: Dict[str, Any]) -> tuple[bool, str]:
    """
    Process Claude API response, handling various response formats.
    
    Args:
        response: The API response dictionary.
        
    Returns:
        Tuple of (success, content).
    """
    try:
        # Check if response contains content
        if 'content' in response:
            # Handle list of content blocks (newer API format)
            if isinstance(response['content'], list):
                # Extract text from content blocks
                text_parts = []
                for block in response['content']:
                    if block.get('type') == 'text':
                        text_parts.append(block.get('text', ''))
                return True, ''.join(text_parts)
            
            # Handle direct content string (older API format)
            elif isinstance(response['content'], str):
                return True, response['content']
        
        # Check if response has a completion field (older API format)
        elif 'completion' in response:
            return True, response['completion']
        
        # Fallback for unknown response format
        return False, f"Unexpected response format: {response}"
    
    except Exception as e:
        return False, f"Error processing Claude response: {e}"
