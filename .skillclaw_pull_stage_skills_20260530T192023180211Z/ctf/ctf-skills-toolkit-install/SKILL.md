---
name: ctf-skills-toolkit-install
description: "Clone, install dependencies, validate scripts, and integrate Huoxing999/ctf-skills into Hermes. For when you need to set up the CTF skills toolkit or audit its scripts. NOT for: running CTF challenges (use in a sandbox), general Python package management, or non-CTF encode/decode tasks."
category: ctf
---

## Install Steps

1. **Clone the repo**:
   bash
   cd ~
   git clone https://github.com/Huoxing999/ctf-skills.git
   
   Expected size: ~2MB. Repo layout includes `ctf-crypto/`, `ctf-reverse/`, `ctf-pwn/`, `ctf-misc/`, `ctf-sqli/`, `ctf-web/`, `ctf-moblie/` (note: repo uses `moblie` typo).

2. **Install Python dependencies**:
   bash
   pip install -r ~/ctf-skills/requirements.txt
   
   If no requirements.txt exists, check individual subdirectories for per-tool dependencies.

3. **Verify all SKILL.md files were pulled**:
   After clone, check that every subdirectory has a SKILL.md (these are the Hermes skill entry points):
   bash
   ls ~/ctf-skills/*/SKILL.md
   

   **If a SKILL.md is missing** (git clone sometimes drops files), download it directly:
   bash
   curl -sL "https://raw.githubusercontent.com/Huoxing999/ctf-skills/main/<subdir>/SKILL.md" -o ~/ctf-skills/<subdir>/SKILL.md
   
   Known case: `ctf-sqli/SKILL.md` is frequently missing after clone. On some systems, `ctf-sqli` subdirectory itself may be missing.

4. **Verify critical tools are importable**:
   bash
   python3 -c "from ctf_crypto.rsa_crt import rsa_crt; print('rsa_crt OK')"
   python3 -c "from ctf_crypto.rsa_common import rsa_common; print('rsa_common OK')"
   

5. **Validate esoteric_decoder.py** (optional but recommended):
   bash
   # CLI validation
   python3 ~/ctf-skills/ctf-misc/esoteric_decoder.py --input ".... . .-.. .-.. ---" --method Morse
   python3 ~/ctf-skills/ctf-misc/esoteric_decoder.py --input "01001000 01001001" --method Binary
   

   Test vectors with expected outputs:
   python
   import sys
   sys.path.insert(0, '/root/ctf-skills/ctf-misc')
   from esoteric_decoder import decode

   # Morse decode (dots/dashes with spaces between letters, `/` = word separator)
   morse_test = "-.-. -.-. / -.-. -.--. -.--. .---- -. -. -.. -.-- .---- --... -.-. -.-. -.."
   print(f"Morse result: {decode(morse_test)}")
   # Expected: CC CYPC1N7CC7D

   # Binary decode (8-bit groups, space-separated)
   binary_test = "01000011 01000011 00100000 01000011 01011001 01010000 01000011 00110001 01001110 01001110 01010100 01001001 01000111"
   print(f"Binary result: {decode(binary_test)}")
   # Expected: CC CYPC1NNTIG
   

## Known Bug: esoteric_decoder.py Brainfuck decoder

**Status**: BROKEN. The `decode_brainfuck` function has a logic bug:
- `bracket_map` is initialized as `{}` before `find_matching_brackets` is called
- When the loop tries to find matching brackets, `bracket_map[char]` returns `None` for all brackets
- The `while cell_value != 0:` loop exits immediately since no brackets are found
- **Result**: empty output for all Brainfuck inputs

Morse and Binary decoders work correctly. Use Morse/Binary for decode tasks; avoid Brainfuck until the bug is fixed.

## Integration

Each subdirectory's SKILL.md is a standalone Hermes skill. After validating, you can `skill_manage(action='read', name='...')` on individual SKILL.md files or load them via the normal skill discovery mechanism.

For programmatic use in Hermes, add to Python path:
python
import sys
sys.path.insert(0, '/root/ctf-skills')
# Now import: from ctf_crypto.rsa_crt import rsa_crt


Or via Hermes config:

{"pythonpath": ["/root/ctf-skills"]}


For a top-level decision tree that routes CTF challenges to the right sub-skill, create a wrapper skill reading from `ctf-crypto/`, `ctf-reverse/`, etc.
