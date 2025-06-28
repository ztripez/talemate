#!/usr/bin/env python3
"""Test script to debug KoboldCpp LiteLLM integration"""
import asyncio
import litellm
import structlog
import logging
import os

# Enable debug logging
os.environ['LITELLM_LOG'] = 'DEBUG'

async def test_kobold_call():
    """Test direct litellm call with custom/koboldcpp"""
    
    # First, let's see what providers litellm knows about
    print("Checking litellm providers...")
    
    # Check if litellm has model_list
    if hasattr(litellm, 'model_list'):
        print(f"Model list: {litellm.model_list}")
    
    # Check if we can get valid models
    try:
        from litellm import get_valid_models
        kobold_models = get_valid_models(custom_llm_provider="koboldcpp")
        print(f"Valid models for koboldcpp: {kobold_models}")
    except Exception as e:
        print(f"Could not get valid models: {e}")
    
    # Test 1: Try with openai compatibility
    print("\n--- Test 1: OpenAI compatibility mode ---")
    params1 = {
        "model": "openai/koboldcpp-model",
        "api_base": "http://127.0.0.1:5001/v1",
        "api_key": "dummy",
        "messages": [{"role": "user", "content": "Say hello"}],
        "temperature": 0.7,
        "max_tokens": 50,
        "drop_params": True
    }
    
    print(f"Calling with: {params1}")
    
    try:
        response = await litellm.acompletion(**params1)
        print(f"Success! Response: {response.choices[0].message.content}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
    
    # Test 2: Try with koboldcpp provider directly
    print("\n--- Test 2: Direct koboldcpp provider ---")
    params2 = {
        "model": "koboldcpp",
        "api_base": "http://127.0.0.1:5001",
        "messages": [{"role": "user", "content": "Say hello"}],
        "temperature": 0.7,
        "max_tokens": 50,
        "drop_params": True
    }
    
    print(f"Calling with: {params2}")
    
    try:
        response = await litellm.acompletion(**params2)
        print(f"Success! Response: {response.choices[0].message.content}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        
    # Test 3: Try with custom/koboldcpp
    print("\n--- Test 3: custom/koboldcpp ---")
    params3 = {
        "model": "custom/koboldcpp",
        "api_base": "http://127.0.0.1:5001",
        "messages": [{"role": "user", "content": "Say hello"}],
        "temperature": 0.7,
        "max_tokens": 50,
        "drop_params": True
    }
    
    print(f"Calling with: {params3}")
    
    try:
        response = await litellm.acompletion(**params3)
        print(f"Success! Response: {response.choices[0].message.content}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_kobold_call())