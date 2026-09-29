#!/usr/bin/env bash
# Compiles src/features/simulation/fixtures/*.ino to .hex for arduino.test.ts (needs arduino-cli with the
# arduino:avr core — devenv shell; on an ARM Mac with ARDUINO_COMPILER_PATH / ARDUINO_CTAGS_PATH, as the server).
# The sketch goes in as C++ next to an empty .ino, like the server does it, so there is no ctags step to go wrong.
set -euo pipefail
cd "$(dirname "$0")/../src/features/simulation/fixtures"
for ino in *.ino; do
  name="${ino%.ino}"
  dir=$(mktemp -d)
  mkdir "$dir/sketch"
  : > "$dir/sketch/sketch.ino"
  # as prepareSketch (@electro/notes-api) has it, prototypes apart: the fixtures do not need them
  { echo '#include <Arduino.h>'
    echo 'extern "C" __attribute__((weak)) int __cxa_atexit(void (*)(void *), void *, void *) { return 0; }'
    echo '__attribute__((weak)) void *__dso_handle;'
    echo '#line 1 "sketch.ino"'; cat "$ino"; } > "$dir/sketch/sketch_code.cpp"
  props=()
  [[ -n "${ARDUINO_COMPILER_PATH:-}" ]] && props+=(--build-property "compiler.path=$ARDUINO_COMPILER_PATH")
  [[ -n "${ARDUINO_CTAGS_PATH:-}" ]] && props+=(--build-property "tools.ctags.path=$ARDUINO_CTAGS_PATH")
  arduino-cli compile --fqbn arduino:avr:uno "${props[@]}" --output-dir "$dir/out" "$dir/sketch" > /dev/null
  cp "$dir/out/sketch.ino.hex" "$name.hex"
  rm -rf "$dir"
  echo "$name.hex"
done
