#!/usr/bin/env python3
"""
One-shot migration: updates all Museum room scripts AND workflow files from Anthropic to Groq API.
"""

import os
import re
from pathlib import Path

MUSEUM_ROOT = Path(__file__).parent


def migrate_content(content):
    c = content
    c = c.replace('ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"',
                  'GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"')
    c = c.replace('"https://api.anthropic.com/v1/messages"',
                  '"https://api.groq.com/openai/v1/chat/completions"')
    c = c.replace('ANTHROPIC_API_URL', 'GROQ_API_URL')
    c = c.replace('os.environ.get("ANTHROPIC_API_KEY"', 'os.environ.get("GROQ_API_KEY"')
    c = c.replace("os.environ.get('ANTHROPIC_API_KEY'", "os.environ.get('GROQ_API_KEY'")
    c = c.replace('"ANTHROPIC_API_KEY"', '"GROQ_API_KEY"')
    c = c.replace("'ANTHROPIC_API_KEY'", "'GROQ_API_KEY'")
    c = re.sub(
        r'"x-api-key":\s*api_key,\s*\n(\s*)"anthropic-version":\s*"[^"]*",',
        '"Authorization": f"Bearer {api_key}",',
        c
    )
    c = re.sub(
        r'"anthropic-version":\s*"[^"]*",\s*\n(\s*)"x-api-key":\s*api_key,',
        '"Authorization": f"Bearer {api_key}",',
        c
    )
    c = re.sub(r'\s*"anthropic-version":\s*"[^"]*",\n', '\n', c)
    c = re.sub(r'"claude-[a-z0-9\-."]+"', '"llama-3.3-70b-versatile"', c)
    c = c.replace('data["content"][0]["text"]', 'data["choices"][0]["message"]["content"]')
    c = c.replace("data['content'][0]['text']", "data['choices'][0]['message']['content']")
    c = re.sub(r'response\.json\(\)\["content"\]\[0\]\["text"\]',
               'response.json()["choices"][0]["message"]["content"]', c)
    c = c.replace('.get("content", [])', '.get("choices", [])')
    c = re.sub(
        r'for block in (\w+):\s*\n\s*if block\.get\("type"\) == "text":\s*\n\s*return block\["text"\]\.strip\(\)',
        r'if \1:\n            return \1[0]["message"]["content"].strip()',
        c
    )
    # Add stub functions in except ImportError block so museum_on_exit is always defined
    if 'except ImportError:' in c and 'def museum_on_exit' not in c.split('except ImportError:')[0]:
        c = c.replace(
            'except ImportError:\n    MUSEUM_INTEGRATED = False',
            'except ImportError:\n    MUSEUM_INTEGRATED = False\n    def museum_on_enter(*args, **kwargs): return {}\n    def museum_on_exit(*args, **kwargs): pass'
        )

    return c


def migrate_python_files():
    changed = []
    for py_file in sorted(MUSEUM_ROOT.rglob('*.py')):
        rel = str(py_file.relative_to(MUSEUM_ROOT))
        if rel in ('migrate_all_rooms.py', 'gen_workflows.py',
                   'integrate_rooms.py', 'add_message_triggers.py'):
            continue
        if 'integration/validate_room' in rel or 'example-room' in rel:
            continue
        try:
            original = py_file.read_text()
        except Exception as e:
            print(f'SKIP {rel}: {e}')
            continue
        if 'api.anthropic.com' not in original and 'ANTHROPIC_API_KEY' not in original:
            continue
        migrated = migrate_content(original)
        if migrated != original:
            py_file.write_text(migrated)
            changed.append(rel)
            print(f'MIGRATED: {rel}')
        else:
            print(f'NO_CHANGE: {rel}')
    print(f'\nPython done: {len(changed)} files migrated')
    return len(changed)


def migrate_workflows():
    """Add GROQ_API_KEY env var to all workflow yml files that use ANTHROPIC_API_KEY."""
    workflows_dir = MUSEUM_ROOT / ".github" / "workflows"
    changed = []
    for yml_file in sorted(workflows_dir.glob("*.yml")):
        try:
            original = yml_file.read_text()
        except Exception as e:
            print(f'SKIP {yml_file.name}: {e}')
            continue
        if 'ANTHROPIC_API_KEY' not in original:
            continue
        if 'GROQ_API_KEY' in original and 'permissions:' in original:
            # Fix duplicates if present
            if original.count('GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}') > 1:
                seen = False
                deduped = []
                for ln in original.split('\n'):
                    if 'GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}' in ln:
                        if not seen:
                            deduped.append(ln)
                            seen = True
                    else:
                        deduped.append(ln)
                yml_file.write_text('\n'.join(deduped))
                changed.append(yml_file.name)
                print(f'DEDUPED: {yml_file.name}')
            else:
                print(f'ALREADY_DONE: {yml_file.name}')
            continue
        lines = original.split('\n')
        new_lines = []
        for line in lines:
            new_lines.append(line)
            if 'ANTHROPIC_API_KEY:' in line and 'secrets.ANTHROPIC_API_KEY' in line:
                indent = len(line) - len(line.lstrip())
                new_lines.append(' ' * indent + 'GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}')
        joined = '\n'.join(new_lines)
        # Add permissions: contents: write if missing
        if 'permissions:' not in joined and 'jobs:' in joined:
            joined = joined.replace('jobs:', 'permissions:\n  contents: write\n\njobs:')
        migrated = joined
        if migrated != original:
            yml_file.write_text(migrated)
            changed.append(yml_file.name)
            print(f'WORKFLOW_MIGRATED: {yml_file.name}')
    print(f'\nWorkflows done: {len(changed)} files updated')
    return len(changed)


def wire_museum_hooks():
    """Wire museum_on_exit(response) after write_visits() in all room scripts."""
    changed = []
    for py_file in sorted(MUSEUM_ROOT.rglob('*.py')):
        rel = str(py_file.relative_to(MUSEUM_ROOT))
        if rel in ('migrate_all_rooms.py', 'gen_workflows.py',
                   'integrate_rooms.py', 'add_message_triggers.py'):
            continue
        if 'integration/validate_room' in rel or 'example-room' in rel:
            continue
        try:
            original = py_file.read_text()
        except Exception as e:
            print(f'SKIP {rel}: {e}')
            continue
        # Only process files that have museum_on_exit defined but not called in main
        if 'def museum_on_exit' not in original:
            continue
        if 'museum_on_exit(response)' in original:
            # Fix stub if missing (for files wired before stubs were added)
            if 'def museum_on_exit(*args' not in original and 'except ImportError:' in original:
                stubbed = original.replace('except ImportError:\n    MUSEUM_INTEGRATED = False', 'except ImportError:\n    MUSEUM_INTEGRATED = False\n    def museum_on_enter(*args, **kwargs): return {}\n    def museum_on_exit(*args, **kwargs): pass')
                if stubbed != original:
                    py_file.write_text(stubbed)
                    changed.append(rel)
                    print(f'STUBS_ADDED: {rel}')
                    continue
            print(f'HOOKS_DONE: {rel}')
            continue
        # Insert museum_on_exit(response) after write_visits(
        lines = original.split('\n')
        new_lines = []
        for line in lines:
            new_lines.append(line)
            stripped = line.strip()
            if stripped.startswith('write_visits(') and 'visit_count' in stripped:
                indent = len(line) - len(line.lstrip())
                new_lines.append(' ' * indent + 'museum_on_exit(response)')
                # Also fix except ImportError stub if needed
        migrated = '\n'.join(new_lines)
        if migrated != original:
            py_file.write_text(migrated)
            changed.append(rel)
            print(f'HOOKS_WIRED: {rel}')
    print(f'\nHooks done: {len(changed)} files updated')
    return len(changed)


def fix_guard_ordering():
    """Move if __name__ == '__main__' to after museum hooks if it comes before them."""
    changed = []
    for py_file in sorted(MUSEUM_ROOT.rglob('*.py')):
        rel = str(py_file.relative_to(MUSEUM_ROOT))
        if rel in ('migrate_all_rooms.py', 'gen_workflows.py',
                   'integrate_rooms.py', 'add_message_triggers.py'):
            continue
        if 'integration/validate_room' in rel or 'example-room' in rel:
            continue
        try:
            original = py_file.read_text()
        except Exception as e:
            print(f'SKIP {rel}: {e}')
            continue
        if '# MUSEUM HOOKS' not in original:
            continue
        if 'museum_on_exit(response)' not in original:
            continue
        lines = original.split('\n')
        guard_idx = next((i for i, l in enumerate(lines) if l.strip() == 'if __name__ == "__main__":'), -1)
        hooks_idx = next((i for i, l in enumerate(lines) if '# MUSEUM HOOKS' in l), -1)
        if guard_idx == -1 or hooks_idx == -1:
            continue
        if guard_idx > hooks_idx:
            print(f'ORDER_OK: {rel}')
            continue
        # Guard comes before hooks — move it to end
        guard_block = lines[guard_idx:guard_idx+2]  # if __name__ + main()
        new_lines = lines[:guard_idx] + lines[guard_idx+2:]
        # Strip trailing blanks and append guard at end
        while new_lines and not new_lines[-1].strip():
            new_lines.pop()
        new_lines += ['', '', 'if __name__ == "__main__":', '    main()', '']
        migrated = '\n'.join(new_lines)
        if migrated != original:
            py_file.write_text(migrated)
            changed.append(rel)
            print(f'GUARD_MOVED: {rel}')
    print(f'\nGuard fix done: {len(changed)} files updated')
    return len(changed)


if __name__ == '__main__':
    migrate_python_files()
    migrate_workflows()
    wire_museum_hooks()
    fix_guard_ordering()
