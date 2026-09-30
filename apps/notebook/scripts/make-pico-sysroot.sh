#!/usr/bin/env bash
# Builds public/arduino/pico.tar: everything the in-browser compiler (clang/lld, as WebAssembly: its ARM
# backend) needs next to a sketch to make a Raspberry Pi Pico program, as arduino-pico (earlephilhower's
# rp2040:rp2040 core, board rpipico) would —
#
#   include/…         the headers: arduino-pico's core and the pico-sdk parts it includes, the libraries
#                     below, newlib's and GCC's libstdc++ (thumb, v6-m) — each where compile.txt says
#   lib/              core.a, lib<Name>.a, boot2.o (compiled by arduino-cli: GCC — the sketch alone is
#                     compiled by clang, the ABI is the same), arduino-pico's libpico.a and ota.o, GCC's
#                     libc, libm, libstdc++, libgcc and crt files (all without debug info)
#   memmap.ld         arduino-pico's linker script, as it fills it in for a Pico (2 MB flash, no file system)
#   compile.txt       clang's flags for a sketch, one a line: the core's defines and include directories
#   link.txt          lld's flags: the core's --wrap and --undefined ones
#
# Used by ../src/features/simulation/compiler/toolchain.ts. Needs nix (llvm's tools, for the
# archives) and arduino-cli with the rp2040:rp2040 core and the libraries (devenv's arduino-setup installs
# them); run in devenv's shell (ARDUINO_CTAGS_PATH on an ARM Mac).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
out="$here/../public/arduino"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

tools=$(nix build --impure --no-link --print-out-paths --expr '
  let pkgs = import (builtins.getFlake "nixpkgs") {};
  in pkgs.symlinkJoin { name = "pico-sysroot-tools"; paths = [ pkgs.llvmPackages_latest.llvm ]; }')
bin="$tools/bin"
data=$(arduino-cli config get directories.data)
core=$(ls -d "$data"/packages/rp2040/hardware/rp2040/* | sort -V | tail -1)
gcc=$(ls -d "$data"/packages/rp2040/tools/pqt-gcc/* | sort -V | tail -1)
cxx=$(ls -d "$gcc"/arm-none-eabi/include/c++/* | sort -V | tail -1)
libgcc=$(ls -d "$gcc"/lib/gcc/arm-none-eabi/*/thumb | sort -V | tail -1)
newlib="$gcc/arm-none-eabi/lib/thumb"

# 1. arduino-cli compiles the core and the libraries once, for a sketch that includes them all; its log
#    says how (the flags for the sketch's own file, and for linking)
LIBRARIES=(SPI Wire EEPROM Servo LiquidCrystal LiquidCrystal_I2C Adafruit_BusIO Adafruit_GFX Adafruit_SSD1306 Adafruit_ILI9341 RTClib)
mkdir -p "$work/sketch"
: > "$work/sketch/sketch.ino"
cat > "$work/sketch/sketch_code.cpp" <<'EOF'
#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>
#include <EEPROM.h>
#include <Servo.h>
#include <LiquidCrystal.h>
#include <LiquidCrystal_I2C.h>
#include <Adafruit_BusIO_Register.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_ILI9341.h>
#include <RTClib.h>
void setup() {}
void loop() {}
EOF
build="$work/build"
arduino-cli compile --fqbn rp2040:rp2040:rpipico --verbose --build-path "$build" --output-dir "$work/out" \
  ${ARDUINO_CTAGS_PATH:+--build-property "tools.ctags.path=$ARDUINO_CTAGS_PATH"} "$work/sketch" > "$work/log.txt"

root="$work/sysroot"
mkdir -p "$root/include" "$root/lib"

# headers of a directory (and below), to include/<where>
headers() { # dir, where
  [[ -d "$1" ]] || return 0
  (cd "$1" && find . \( -name '*.h' -o -name '*.hpp' -o -name '*.inc' \) -type f) | while read -r h; do
    mkdir -p "$root/include/$2/$(dirname "$h")"
    cp "$1/$h" "$root/include/$2/$h"
  done
}

# 2. the sketch's flags, from how arduino-cli compiled it: the defines as they are (response files
#    unfolded), the include directories as directories of include/ (the core's, the libraries')
line=$(grep -- '-c .*sketch/sketch_code.cpp -o .*sketch_code.cpp.o' "$work/log.txt" | head -1)
eval "set -- $line"
flags=() prefix=""
unfold() { tr -d '\r' < "$1" | grep -v '^$'; }
while (($#)); do
  arg=$1; shift
  case "$arg" in
    @*) mapfile -t more < <(unfold "${arg#@}"); set -- "${more[@]}" "$@" ;;
    -iprefix*) prefix=${arg#-iprefix} ;;
    -iwithprefixbefore*|-iwithprefix*|-I*)
      dir=${arg#-iwithprefixbefore}; dir=${dir#-iwithprefix}; dir=${dir#-I}
      [[ "$arg" == -I* ]] || dir="$prefix$dir"
      case "$dir" in
        "$build"*) continue ;;  # (the build's own directories)
        "$core"*) where="core${dir#"$core"}" ;;
        */libraries/*) where="libraries/${dir##*/libraries/}" ;;  # (the Library Manager's)
        *) continue ;;
      esac
      where=${where//\/\//\/}
      headers "$dir" "$where"
      flags+=("-I/pico/include/$where") ;;
    -D*|-U*) flags+=("$arg") ;;
  esac
done
# and every header the build read (arduino-cli's .d files), wherever it is: some are included by a path
# relative to another (../generic/common.h), not from an include directory
find "$build" -name '*.d' -exec cat {} + | tr ' \\' '\n\n' | grep -E '\.(h|hpp|inc)$' | sort -u | while read -r h; do
  case "$h" in
    "$core"/*) where="core/${h#"$core"/}" ;;
    */libraries/*) where="libraries/${h##*/libraries/}" ;;
    *) continue ;;
  esac
  mkdir -p "$root/include/$(dirname "$where")"
  cp "$h" "$root/include/$where"
done
cp -R "$cxx" "$root/include/cxx"  # (its headers have no .h)
cp -R "$cxx/arm-none-eabi/thumb" "$root/include/cxx-thumb"
rm -rf "$root/include/cxx/arm-none-eabi" "$root/include/cxx-thumb/autofp"
headers "$gcc/arm-none-eabi/include" newlib
rm -rf "$root/include/newlib/c++"
printf '%s\n' "${flags[@]}" -isystem /pico/include/cxx -isystem /pico/include/cxx-thumb -isystem /pico/include/cxx/backward \
  -isystem /pico/include/newlib > "$root/compile.txt"
chmod -R u+w "$root"

# 3. the link: the core's --wrap and --undefined flags, and -u
line=$(grep -- ' -o .*sketch.ino.elf' "$work/log.txt" | head -1)
eval "set -- $line"
link=()
while (($#)); do
  arg=$1; shift
  case "$arg" in
    @*) mapfile -t more < <(unfold "${arg#@}"); set -- "${more[@]}" "$@" ;;
    -Wl,--wrap=*|-Wl,--undefined=*) link+=("${arg#-Wl,}") ;;
    -u) link+=(-u "$1"); shift ;;
  esac
done
printf '%s\n' "${link[@]}" | awk '!seen[$0]++ || $0 == "-u"' > "$root/link.txt"

# 4. what is linked in: the core and the libraries arduino-cli compiled, arduino-pico's and GCC's own
strip() { "$bin/llvm-objcopy" --strip-debug "$1" "$2"; }
strip "$build/core/core.a" "$root/lib/core.a"
strip "$build/boot2.o" "$root/lib/boot2.o"
for name in "${LIBRARIES[@]}"; do
  dir=$(ls -d "$build"/libraries/"$name"* | head -1)
  objs=$(find "$dir" -name '*.o'); archives=$(find "$dir" -name '*.a')
  mkdir -p "$work/lib-$name"
  for a in $archives; do (cd "$work/lib-$name" && "$bin/llvm-ar" x "$a"); done
  for o in $objs; do cp "$o" "$work/lib-$name/"; done
  if compgen -G "$work/lib-$name/*.o" > /dev/null; then
    "$bin/llvm-ar" rcs "$work/lib$name.a" "$work/lib-$name"/*.o
    strip "$work/lib$name.a" "$root/lib/lib$name.a"
  fi
done
strip "$core/lib/rp2040/libpico.a" "$root/lib/libpico.a"
strip "$core/lib/rp2040/ota.o" "$root/lib/ota.o"
for f in libc.a libm.a libstdc++.a crt0.o; do strip "$newlib/$f" "$root/lib/$f"; done
for f in libgcc.a crti.o crtbegin.o crtend.o crtn.o; do strip "$libgcc/$f" "$root/lib/$f"; done
cp "$build/memmap_default.ld" "$root/memmap.ld"

mkdir -p "$out"
(cd "$root" && tar --format=ustar -cf "$out/pico.tar" .)
ls -la "$out/pico.tar"
