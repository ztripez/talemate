"""
Test narrator agent with clean prompt system and instructor.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from talemate.agents.narrator import NarratorAgent
from talemate.client.instructor_models import NarratorResponse
from talemate.model_preset import ModelPreset


@pytest.fixture
def mock_model_preset():
    """Create a mock ModelPreset for testing"""
    preset = MagicMock(spec=ModelPreset)
    preset.provider_name = "test_provider"
    preset.model_name = "test_model"
    preset.get_provider.return_value = MagicMock()
    preset.get_client.return_value = MagicMock()
    preset.request_clean = AsyncMock()
    return preset


@pytest.fixture 
def mock_scene():
    """Create a mock scene for testing"""
    scene = MagicMock()
    scene.config = {}
    scene.get_player_character.return_value = MagicMock()
    scene.get_npc_characters.return_value = []
    scene.get_characters.return_value = []
    scene.history = []
    scene.agent_state = {}
    return scene


def test_narrator_agent_instantiation_with_model_preset(mock_model_preset):
    """Test that NarratorAgent can be instantiated with ModelPreset"""
    agent = NarratorAgent(model_preset=mock_model_preset)
    
    assert agent.model_preset == mock_model_preset
    assert agent.client is not None  # Should get client from model preset
    assert hasattr(agent, 'actions')
    assert agent.agent_type == "narrator"


@pytest.mark.asyncio
async def test_narrator_request_with_instructor(mock_model_preset, mock_scene):
    """Test that narrator can use request_with_instructor method"""
    # Setup mock response
    mock_response = NarratorResponse(narration="Test narration response")
    mock_model_preset.request_clean.return_value = mock_response
    
    # Create narrator agent
    agent = NarratorAgent(model_preset=mock_model_preset)
    agent.connect(mock_scene)
    
    # Test request_with_instructor
    response = await agent.request_with_instructor(
        "test-template",
        vars={"scene": mock_scene},
        response_model=NarratorResponse
    )
    
    # Verify the request was made correctly
    mock_model_preset.request_clean.assert_called_once_with(
        "narrator.test-template",
        {"scene": mock_scene},
        response_model=NarratorResponse
    )
    
    # Verify response
    assert response == mock_response


@pytest.mark.asyncio
async def test_narrator_narrate_scene_with_clean_prompts(mock_model_preset, mock_scene):
    """Test narrate_scene method uses clean prompt system"""
    # Setup mock response
    mock_response = NarratorResponse(narration="The scene unfolds dramatically.")
    mock_model_preset.request_clean.return_value = mock_response
    
    # Create narrator agent
    agent = NarratorAgent(model_preset=mock_model_preset)
    agent.connect(mock_scene)
    
    # Mock emit_status to avoid emission during test
    agent.emit_status = AsyncMock()
    
    # Test narrate_scene
    with patch('talemate.agents.narrator.active_agent'), \
         patch('talemate.emit.async_signals'):
        result = await agent.narrate_scene("Test narrative direction")
    
    # Verify clean prompt was used
    mock_model_preset.request_clean.assert_called()
    call_args = mock_model_preset.request_clean.call_args
    
    # Check that it called with narrator.narrate-scene template
    assert call_args[0][0] == "narrator.narrate-scene"
    assert call_args[1]["response_model"] == NarratorResponse
    
    # Verify the result is cleaned
    assert result == "The scene unfolds dramatically."


@pytest.mark.asyncio 
async def test_narrator_fallback_when_clean_prompt_fails(mock_model_preset, mock_scene):
    """Test that narrator falls back gracefully when clean prompt system fails"""
    # Setup model preset to fail
    mock_model_preset.request_clean.side_effect = Exception("Clean prompt failed")
    
    # Create narrator agent
    agent = NarratorAgent(model_preset=mock_model_preset)
    agent.connect(mock_scene)
    agent.emit_status = AsyncMock()
    
    # Mock the fallback Prompt.request method
    with patch('talemate.prompts.Prompt.request', new_callable=AsyncMock) as mock_prompt_request, \
         patch('talemate.agents.narrator.active_agent'), \
         patch('talemate.emit.async_signals'):
        
        mock_prompt_request.return_value = "Fallback narration"
        
        result = await agent.narrate_scene("Test narrative direction")
        
        # Verify fallback was called
        mock_prompt_request.assert_called_once()
        assert result == "Fallback narration"


def test_narrator_clean_result_method():
    """Test narrator's clean_result method works correctly"""
    agent = NarratorAgent()
    
    # Test basic cleaning
    result = agent.clean_result("Test narration.")
    assert result == "Test narration."
    
    # Test stripping colons
    result = agent.clean_result(": Test narration with colon prefix.")
    assert result == "Test narration with colon prefix."
    
    # Test comment removal
    result = agent.clean_result("Good narration.\n# This is a comment\nMore narration.")
    assert "# This is a comment" not in result
    assert "Good narration." in result
    assert "More narration." in result