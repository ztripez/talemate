"""
Clean prompt handler for LiteLLM providers with instructor support.

This module provides a simplified prompt handling system that removes
all the output formatting and coercion logic from the legacy prompt system,
relying instead on instructor for structured output validation.
"""

import structlog
from typing import Any, Dict, Optional

from talemate.prompts.base import Prompt
from talemate.util.prompt import condensed, no_chapters

log = structlog.get_logger("talemate.llm_providers.prompt_handler")


class CleanPrompt(Prompt):
    """
    Clean prompt handler that removes formatting concerns while keeping Jinja2 power.
    Used with LiteLLM providers that have instructor support.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Disable all formatting/coercion features
        self.data_response = False
        self.eval_response = False
        self.prepared_response = ""
        self.pad_prepended_response = False
        self.dedupe_enabled = False
        self.sectioning_hander = "none"  # No sectioning
        
    def render(self):
        """Override to provide clean rendering without formatting tricks"""
        env = self.template_env()
        
        # Add the essential filters that templates expect
        env.filters["condensed"] = condensed
        env.filters["no_chapters"] = no_chapters
        
        # Build context with only what's needed for content generation
        ctx = {
            # Core template utilities
            "render_template": self.render_template,
            "debug": lambda *a, **kw: log.debug(*a, **kw),
            
            # Scene and memory queries
            "query_scene": self.query_scene,
            "query_memory": self.query_memory,
            "query_text": self.query_text,
            "query_text_eval": self.query_text_eval,
            "instruct_text": self.instruct_text,
            
            # Agent utilities
            "agent_action": self.agent_action,
            "agent_config": self.agent_config,
            "retrieve_memories": self.retrieve_memories,
            
            # Basic utilities
            "time_diff": self.time_diff,
            "random": self.random,
            "random_as_str": lambda x, y: str(self.random(x, y)),
            "random_choice": lambda x: self.random_choice(x),
            "uuidgen": lambda: str(self.uuidgen()),
            "to_int": lambda x: int(x),
            "to_str": lambda x: str(x),
            "len": lambda x: len(x),
            "max": lambda x, y: max(x, y),
            "min": lambda x, y: min(x, y),
            "join": lambda x, y: y.join(x),
            "make_list": lambda: [],
            "make_dict": lambda: {},
            
            # Empty/disabled formatting helpers
            "bot_token": "",
            
            # Status emission (useful for long operations)
            "emit_status": self.emit_status,
            "emit_system": lambda status, message: self.emit_system(status, message) if hasattr(self, 'emit_system') else None,
            
            # Text utilities
            "text_to_chunks": self.text_to_chunks,
            "count_tokens": lambda x: self.count_tokens(x) if hasattr(self, 'count_tokens') else 0,
            
            # Config access
            "config": self.config,
            
            # Context from agents
            "active_agent": self.vars.get('active_agent'),
            "agent_context_state": self.vars.get('agent_context_state', {}),
            
            # No formatting helpers - these are intentionally removed:
            # - bot_token
            # - set_prepared_response*
            # - set_json_response
            # - set_data_response
            # - set_eval_response
            # - set_question_eval
            # - disable_dedupe
            # - llm_can_be_coerced
        }
        
        # Add template variables
        ctx.update(self.vars)
        
        # Default decensor to False if not specified
        if "decensor" not in ctx:
            ctx["decensor"] = False
        
        # Load template
        if self.template:
            # Use inline template if provided
            template = env.from_string(self.template)
        else:
            # Load from file
            template_name = self.name
            try:
                template = env.get_template(f"{template_name}.jinja2")
            except Exception as e:
                log.error(f"Failed to load template {template_name}: {e}")
                raise
        
        # Render without second pass, deduping, or sectioning
        try:
            self.prompt = template.render(ctx).strip()
        except Exception as e:
            log.error(f"Failed to render template: {e}")
            raise
        
        return self.prompt
        
    async def send(self, client: Any = None, kind: str = "create"):
        """Override to skip all response formatting logic"""
        # Just render and return - no prepared response handling
        # The actual sending is handled by the ModelPreset
        return self.render()
        
    def count_tokens(self, text: str) -> int:
        """Simple token counting without deduplication"""
        # Rough estimate: 1 token per 4 characters
        return len(text) // 4
        
    def random_choice(self, choices):
        """Helper for random choice in templates"""
        import random
        return random.choice(choices)
        
    def uuidgen(self):
        """Helper for UUID generation in templates"""
        import uuid
        return uuid.uuid4()
        
    def emit_system(self, status: str, message: str):
        """Helper to emit system messages from templates"""
        from talemate.emit import emit
        emit("system", status=status, message=message)