#!/usr/bin/env python3
"""Test system prompt loading"""

from src.talemate.client.system_prompts import render_prompt

# Test what prompts are being returned
narrator_normal = render_prompt('narrator', decensor=False)
narrator_decensor = render_prompt('narrator', decensor=True)

print('Normal narrator prompt (first 200 chars):')
print(repr(narrator_normal[:200]))
print()
print('Decensor narrator prompt (first 200 chars):')
print(repr(narrator_decensor[:200]))
print()
print('Are they different?', narrator_normal != narrator_decensor)
print('Normal prompt length:', len(narrator_normal))
print('Decensor prompt length:', len(narrator_decensor))

# Test other agent types
director_normal = render_prompt('director', decensor=False)
director_decensor = render_prompt('director', decensor=True)

print()
print('Director normal vs decensor different?', director_normal != director_decensor)