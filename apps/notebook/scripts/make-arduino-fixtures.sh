#!/usr/bin/env bash
# Compiles src/features/simulation/fixtures/*.ino for the tests (needs arduino-cli with the arduino:avr
# and rp2040:rp2040 cores — devenv shell; on an ARM Mac with ARDUINO_COMPILER_PATH / ARDUINO_CTAGS_PATH,
# as the sysroot scripts): NAME.ino to NAME.hex for an Uno, NAME.pico.ino to NAME.pico.bin (the flash image) for a Pico.
# The sketch goes in as C++ next to an empty .ino (as compiler/sketch.ts makes it), so there is no ctags step to go wrong.
set -euo pipefail
cd "$(dirname "$0")/../src/features/simulation/fixtures"
for ino in *.ino; do
  name="${ino%.ino}"
  dir=$(mktemp -d)
  mkdir "$dir/sketch"
  : > "$dir/sketch/sketch.ino"
  # as prepareSketch (compiler/sketch.ts) has it, prototypes apart: the fixtures do not need them
  { echo '#include <Arduino.h>'
    echo 'extern "C" __attribute__((weak)) int __cxa_atexit(void (*)(void *), void *, void *) { return 0; }'
    echo '__attribute__((weak)) void *__dso_handle;'
    echo '#line 1 "sketch.ino"'; cat "$ino"; } > "$dir/sketch/sketch_code.cpp"
  props=()
  [[ -n "${ARDUINO_CTAGS_PATH:-}" ]] && props+=(--build-property "tools.ctags.path=$ARDUINO_CTAGS_PATH")
  if [[ "$name" == *.pico ]]; then
    arduino-cli compile --fqbn rp2040:rp2040:rpipico ${props[@]+"${props[@]}"} --output-dir "$dir/out" "$dir/sketch" > /dev/null
    cp "$dir/out/sketch.ino.bin" "$name.bin"
    echo "$name.bin"
  else # (the AVR compiler given is the AVR core's only)
    [[ -n "${ARDUINO_COMPILER_PATH:-}" ]] && props+=(--build-property "compiler.path=$ARDUINO_COMPILER_PATH")
    arduino-cli compile --fqbn arduino:avr:uno ${props[@]+"${props[@]}"} --output-dir "$dir/out" "$dir/sketch" > /dev/null
    cp "$dir/out/sketch.ino.hex" "$name.hex"
    echo "$name.hex"
  fi
  rm -rf "$dir"
done
