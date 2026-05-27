---
name: ctf-apk-time-capsule-solution
description: "Documents the step-by-step solution for the 'Museum Time Capsule' CTF challenge involving an Android APK with four-stage password verification. Use when analyzing APK files, decompiling DEX to Java, or reverse-engineering native JNI libraries for password extraction. NOT for: general mobile security audits, APK repackaging, or non-CTF APK analysis."
category: general
---

---
name: ctf-apk-time-capsule-solution
description: Step-by-step solution for the 'Museum Time Capsule' CTF challenge — an Android APK with four-stage password verification where Parts 1-2 are in Java bytecode and Parts 3-4 are in a native JNI library.
category: ctf
tags:
  - ctf
  - apk
  - reverse-engineering
  - android
  - jni
  - native-library
---

# Museum Time Capsule — CTF Solution

## Challenge Overview

The APK implements a four-stage password verification mechanism:

| Stage | Location | Status |
|-------|----------|--------|
| Part 1 | Java (MainActivity) | ✅ Cracked |
| Part 2 | Java (VerifyUtil) | ✅ Cracked |
| Part 3 | Native library (libtime_capsule.so) | 🔒 Uncracked |
| Part 4 | Native library (libtime_capsule.so) | 🔒 Uncracked |

## Stage 1 & 2 — Java Decompilation

1. Pull the APK from the device or emulator:
   bash
   adb pull /data/app/<package>/base.apk ./time_capsule.apk
   

2. Extract the APK contents:
   bash
   unzip time_capsule.apk -d apk_extracted/
   

3. Decompile the DEX file using `jadx`:
   bash
   jadx -d apk_decompiled apk_extracted/classes.dex
   

4. Navigate to the source in `apk_decompiled/sources/` and locate:
   - `MainActivity` — contains Part 1 of the password.
   - `VerifyUtil` — contains Part 2 of the password.

5. Read the decompiled Smali or Java code to extract the strings or logic that yield Parts 1 and 2.

## Stage 3 & 4 — Native Library Reverse Engineering

The remaining parts are embedded in the native library `libtime_capsule.so`.

1. Extract the native library from the APK:
   bash
   cp apk_extracted/lib/<abi>/libtime_capsule.so ./
   
   Replace `<abi>` with the target architecture (e.g., `arm64-v8a`, `armeabi-v7a`).

2. Check the binary for exported JNI functions:
   bash
   nm -D libtime_capsule.so          # list dynamic symbols
   readelf -s libtime_capsule.so     # symbol table
   

3. Disassemble the library:
   bash
   objdump -d libtime_capsule.so > libtime_capsule.asm
   

4. Open `libtime_capsule.so` in **Ghidra** or **IDA Pro** for deeper analysis:
   - Identify the JNI export table — look for functions named `Java_com_museum_*`.
   - Trace the password verification flow in the native code.
   - Strings embedded in the `.rodata` section may reveal Part 3 or 4 directly.

5. Key things to look for:
   - Embedded XOR or encoding operations that decode the password at runtime.
   - Function calls that compare input against hardcoded values in the native binary.
   - Obfuscation techniques (string encryption, control flow flattening).

## Final Password Assembly

Once all four parts are extracted, concatenate them in order:

[Part1][Part2][Part3][Part4]


## Tools Used

- `adb` — Android Debug Bridge
- `unzip` — APK extraction
- `jadx` — DEX to Java decompiler
- `nm` / `readelf` — ELF symbol inspection
- `objdump` — Disassembly
- `Ghidra` / `IDA Pro` — Native binary reverse engineering

## Tips

- Always inspect multiple ABIs if the APK ships libs for `arm64-v8a`, `armeabi-v7a`, and `x86_64` — string sections may differ slightly.
- Use `strings libtime_capsule.so` as a quick scan before full disassembly.
- If the native code is heavily obfuscated, focus on cross-referencing JNI function strings and input validation logic.

