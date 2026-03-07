"""
Configuration manager for portfolio builder.
Loads and validates config.json, provides easy access to settings.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List


class ConfigManager:
    """Load and manage portfolio configuration."""
    
    def __init__(self, config_path: str = None):
        """
        Initialize config manager.
        
        Args:
            config_path: Path to config.json. If None, uses default in script directory.
        """
        if config_path is None:
            # Default: look for config.json in same directory as this script
            config_path = Path(__file__).parent / "config.json"
        
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load config from JSON file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            return config
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {e}")
    
    def _validate_config(self):
        """Validate config structure and values."""
        required_sections = ["personas", "scoring_weights", "fundamentals", "screening"]
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required section in config: {section}")
        
        # Validate personas
        if not self.config["personas"]:
            raise ValueError("At least one persona must be defined")
        
        for persona_name, persona in self.config["personas"].items():
            required_fields = ["display_name", "description", "stocks_in_portfolio", "constraints"]
            for field in required_fields:
                if field not in persona:
                    raise ValueError(f"Persona '{persona_name}' missing field: {field}")
            
            constraints = persona["constraints"]
            if "max_weight_per_stock" not in constraints or "max_sector_cap" not in constraints:
                raise ValueError(f"Persona '{persona_name}' missing constraint fields")
        
        # Validate scoring weights sum to approximately 1.0
        weights_sum = sum(self.config["scoring_weights"].values())
        if abs(weights_sum - 1.0) > 0.01:
            raise ValueError(f"Scoring weights must sum to 1.0, got {weights_sum}")
    
    def get_personas(self) -> Dict[str, Dict[str, Any]]:
        """Get all personas."""
        return self.config["personas"]
    
    def get_persona(self, persona_name: str) -> Dict[str, Any]:
        """Get specific persona."""
        if persona_name not in self.config["personas"]:
            raise ValueError(f"Persona not found: {persona_name}")
        return self.config["personas"][persona_name]
    
    def get_persona_names(self) -> List[str]:
        """Get list of all persona names."""
        return list(self.config["personas"].keys())
    
    def get_persona_display_names(self) -> Dict[str, str]:
        """Get mapping of persona name to display name."""
        return {
            name: persona["display_name"] 
            for name, persona in self.config["personas"].items()
        }
    
    def get_scoring_weights(self) -> Dict[str, float]:
        """Get scoring model weights."""
        return self.config["scoring_weights"]
    
    def get_fundamentals_config(self) -> Dict[str, Dict[str, Any]]:
        """Get fundamentals metrics configuration."""
        return self.config["fundamentals"]
    
    def get_screening_config(self) -> Dict[str, Any]:
        """Get screening configuration."""
        return self.config["screening"]
    
    def get_persona_constraints(self, persona_name: str) -> Dict[str, Any]:
        """Get constraints for a specific persona."""
        persona = self.get_persona(persona_name)
        return persona["constraints"]
    
    def get_stocks_in_portfolio(self, persona_name: str) -> int:
        """Get number of stocks to include for a persona."""
        persona = self.get_persona(persona_name)
        return persona["stocks_in_portfolio"]
    
    def get_asset_allocation(self, persona_name: str) -> Dict[str, float]:
        """Get asset allocation for a persona (stocks, bonds, defensive_etfs)."""
        persona = self.get_persona(persona_name)
        return persona.get("asset_allocation", {"stocks": 1.0, "bonds": 0.0, "defensive_etfs": 0.0})
    
    def get_asset_universe(self) -> Dict[str, List[Dict]]:
        """Get bond and ETF universe."""
        return self.config.get("asset_universe", {"bonds": [], "defensive_etfs": []})
    
    def get_persona_constraints_with_overrides(self, persona_name: str, overrides: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get constraints for a persona, optionally merged with user overrides.
        
        Args:
            persona_name: Name of persona
            overrides: Optional dict of constraint overrides (e.g., {'max_weight_per_stock': 0.10})
            
        Returns:
            Merged constraints dict
        """
        constraints = self.get_persona_constraints(persona_name).copy()
        if overrides:
            constraints.update(overrides)
        return constraints
    
    def get_stocks_in_portfolio_with_override(self, persona_name: str, override: int = None) -> int:
        """Get stocks count, with optional user override."""
        if override is not None:
            return override
        return self.get_stocks_in_portfolio(persona_name)


# Global config instance
_config_instance = None


def get_config() -> ConfigManager:
    """Get global config instance (singleton pattern)."""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance


def reload_config():
    """Reload config from disk (useful for testing)."""
    global _config_instance
    _config_instance = ConfigManager()
