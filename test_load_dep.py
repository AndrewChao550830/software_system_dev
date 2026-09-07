import sys
sys.path.insert(0, r'c:\Shares\Coding\Assets\00 - software_system_dev')
from orchestrator import load_skill
try:
    skill = load_skill('skill_dep_security')
    print('Skill loaded successfully!')
    print(f'Skill ID: {skill.meta["id"]}')
    print(f'Skill Name: {skill.meta["name"]}')
    print(f'Skill Description: {skill.meta["description"][:100]}...')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()