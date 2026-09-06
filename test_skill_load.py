#!/usr/bin/env python
import sys
import os
sys.path.insert(0, os.getcwd())

try:
    from orchestrator import load_skill
    print("Import successful")
    skill = load_skill('my-code-standard')
    print(f"Skill loaded successfully!")
    print(f'Skill ID: {skill.meta["id"]}')
    print(f'Skill Name: {skill.meta["name"]}')
    print(f'Skill Description: {skill.meta["description"][:100]}...')
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()