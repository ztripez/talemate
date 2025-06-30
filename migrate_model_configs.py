#!/usr/bin/env python3
"""
Migration script to convert model_configs to model_presets.
Run this once to migrate your existing configuration.
"""

import yaml
import sys
from pathlib import Path

def migrate_config(config_path="config.yaml"):
    """Migrate model_configs to model_presets in config.yaml"""
    
    # Load existing config
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"Config file {config_path} not found")
        return False
    
    # Check if migration needed
    if not config.get('model_configs'):
        print("No model_configs found - nothing to migrate")
        return True
        
    if config.get('model_presets'):
        print("model_presets already exists - skipping migration")
        return True
    
    # Create backup
    backup_path = f"{config_path}.backup"
    with open(backup_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    print(f"Created backup: {backup_path}")
    
    # Convert model_configs to model_presets
    model_presets = {}
    
    for config_id, model_config_data in config['model_configs'].items():
        try:
            # Extract provider info
            provider_info = model_config_data.get("provider", {})
            provider_name = provider_info.get("provider_name", "")
            provider_instance_id = provider_info.get("provider_id", "")
            
            # Extract model info
            model_info = model_config_data.get("model", {})
            model_name = model_info.get("name", "")
            model_full_name = model_info.get("full_name", "")
            capabilities = model_info.get("capabilities", {})
            
            # Extract parameters
            parameters = model_config_data.get("parameters", {})
            
            # Extract max context size
            max_context_size = model_info.get("max_context_size") or parameters.get("max_context_size")
            if max_context_size:
                max_context_size = int(max_context_size)
            
            # Create ModelPresetConfig
            model_presets[config_id] = {
                "config_id": config_id,
                "provider_name": provider_name,
                "model_name": model_name,
                "model_full_name": model_full_name,
                "provider_instance_id": provider_instance_id,
                "capabilities": capabilities,
                "parameters": parameters,
                "max_context_size": max_context_size,
                "double_coercion": None,
                "system_prompts": {},
                "enabled": True
            }
            
            print(f"Migrated: {config_id} ({model_name})")
            
        except Exception as e:
            print(f"Failed to migrate {config_id}: {e}")
            continue
    
    # Add model_presets to config
    config['model_presets'] = model_presets
    
    # Remove old model_configs
    del config['model_configs']
    
    # Save migrated config
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    print(f"Migration complete! Migrated {len(model_presets)} models")
    print(f"Old config backed up to: {backup_path}")
    print("You can now delete the backup file if everything works correctly")
    
    return True

if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    success = migrate_config(config_path)
    sys.exit(0 if success else 1)