#!/usr/bin/env python3
"""
Configuration Manager

Handles loading, validating, and accessing configuration settings for the NewsAnalyst application.
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages application configuration from YAML file and command line arguments."""
    
    DEFAULT_CONFIG_PATH = "config.yaml"
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Path to the configuration file (optional)
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.
        
        Returns:
            Dict containing configuration settings
        """
        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"Configuration file not found at {self.config_path}, using defaults")
                return self._get_default_config()
                
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                
            logger.info(f"Loaded configuration from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return self._get_default_config()
            
    def _get_default_config(self) -> Dict[str, Any]:
        """
        Get default configuration settings.
        
        Returns:
            Dict containing default configuration
        """
        return {
            "api": {
                "claude": {
                    "api_key": "",
                    "env_var_name": "ANTHROPIC_API_KEY",
                    "onepassword": {
                        "enabled": False,
                        "vault": "Private",
                        "item": "Anthropic API Key",
                        "field": "api_key"
                    }
                }
            },
            "model": {
                "name": "claude-3-7-sonnet-20250219",
                "temperature": 0.3,
                "max_tokens": 4096
            },
            "prompts": {
                "system_prompt": "prompts/system_prompt.txt",
                "initial_prompt": "prompts/initial_prompt.txt",
                "introspection_prompt": "prompts/introspection_prompt.txt",
                "output_format_prompt": "prompts/output_format.txt"
            },
            "output": {
                "directory": "output"
            },
            "logging": {
                "level": "INFO",
                "file": "newsanalyst.log"
            }
        }
        
    def update_from_args(self, args: Dict[str, Any]) -> None:
        """
        Update configuration with command line arguments.
        
        Args:
            args: Command line arguments as a dictionary
        """
        # API settings
        if args.get('api_key'):
            self.config['api']['claude']['api_key'] = args['api_key']
            
        if args.get('op_vault'):
            self.config['api']['claude']['onepassword']['vault'] = args['op_vault']
            self.config['api']['claude']['onepassword']['enabled'] = True
            
        if args.get('op_item'):
            self.config['api']['claude']['onepassword']['item'] = args['op_item']
            
        if args.get('op_field'):
            self.config['api']['claude']['onepassword']['field'] = args['op_field']
            
        # Model settings
        if args.get('model'):
            self.config['model']['name'] = args['model']
            
        if args.get('temperature') is not None:
            self.config['model']['temperature'] = args['temperature']
            
        if args.get('max_tokens') is not None:
            self.config['model']['max_tokens'] = args['max_tokens']
            
        # Prompt settings
        if args.get('system_prompt'):
            self.config['prompts']['system_prompt'] = args['system_prompt']
            
        if args.get('initial_prompt'):
            self.config['prompts']['initial_prompt'] = args['initial_prompt']
            
        if args.get('introspection_prompt'):
            self.config['prompts']['introspection_prompt'] = args['introspection_prompt']
            
        if args.get('output_format_prompt'):
            self.config['prompts']['output_format_prompt'] = args['output_format_prompt']
            
        # Output settings
        if args.get('output_dir'):
            self.config['output']['directory'] = args['output_dir']
            
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key.
        
        Args:
            key: Dot-separated key path (e.g., 'api.claude.env_var_name')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
            
    def save(self) -> None:
        """Save the current configuration to the YAML file."""
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
