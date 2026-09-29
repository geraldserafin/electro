#!/usr/bin/env bash
# Builds public/arduino/sysroot.tar: everything the in-browser compiler (clang/lld for AVR, as
# WebAssembly) needs next to a sketch to make an Arduino Uno program, prebuilt here once —
#
#   include/          avr-libc's headers (only the ATmega328P's registers)
#   core/             the Arduino core's headers and the Uno's pins_arduino.h
#   libraries/<Name>/ headers of the bundled libraries (SPI, Wire, EEPROM, SoftwareSerial, Servo, LiquidCrystal)
#   lib/              crt, libc, libm, libgcc (without debug info: lld does not read gcc's), core.a,
#                     lib<Name>.a — the core and libraries compiled by clang
#   avr5.x            the GNU linker script for the avr5 family, in the syntax lld reads
#
# The same compiler flags as the browser uses are in ../src/features/arduino/toolchain.ts (FLAGS).
# Needs nix (it fetches clang, avr-libc and avr-gcc's libgcc) and arduino-cli with the arduino:avr
# core and the Servo and LiquidCrystal libraries (devenv's notes-server installs them).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
out="$here/../public/arduino"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

tools=$(nix build --impure --no-link --print-out-paths --expr '
  let pkgs = import (builtins.getFlake "nixpkgs") {};
      avr = pkgs.pkgsCross.avr;
  in pkgs.symlinkJoin { name = "arduino-sysroot-tools"; paths = [
    pkgs.llvmPackages_latest.clang-unwrapped pkgs.llvmPackages_latest.lld pkgs.llvmPackages_latest.llvm
    (pkgs.runCommand "avr-parts" {} "mkdir -p $out/avr-libc $out/libgcc; cp -r ${avr.avrlibc}/avr/* $out/avr-libc/; cp ${avr.buildPackages.gcc.cc}/lib/gcc/avr/*/avr5/libgcc.a $out/libgcc/; cp ${avr.buildPackages.binutils.bintools}/avr/lib/ldscripts/avr5.x $out/")
  ]; }')
bin="$tools/bin"
data=$(arduino-cli config get directories.data)
user=$(arduino-cli config get directories.user)
avr=$(ls -d "$data"/packages/arduino/hardware/avr/* | sort -V | tail -1)
servo="$user/libraries/Servo/src"
lcd="$user/libraries/LiquidCrystal/src"

root="$work/sysroot"
mkdir -p "$root/include" "$root/core" "$root/lib" "$root/libraries"

# avr-libc: headers (registers of the ATmega328P only — io.h picks the chip's file by -mmcu), libraries
cp -RL "$tools/avr-libc/include/." "$root/include/"  # -L: the files, not links into the nix store (BSD cp keeps links)
chmod -R u+w "$root"
find "$root/include/avr" -name 'io*.h' ! -name 'io.h' ! -name 'iom328p.h' -delete
for f in crtatmega328p.o libc.a libm.a libatmega328p.a; do "$bin/llvm-objcopy" --strip-debug "$tools/avr-libc/lib/avr5/$f" "$root/lib/$f"; done
"$bin/llvm-objcopy" --strip-debug "$tools/libgcc/libgcc.a" "$root/lib/libgcc.a"
# GNU ld's SORT(*)(.ctors) is *(SORT(.ctors)) for lld
sed -e 's/KEEP(SORT(\*)(\.ctors))/KEEP(*(SORT(.ctors)))/' -e 's/KEEP(SORT(\*)(\.dtors))/KEEP(*(SORT(.dtors)))/' "$tools/avr5.x" > "$root/avr5.x"

# the Arduino core
cp "$avr"/cores/arduino/*.h "$root/core/"
cp "$avr"/variants/standard/pins_arduino.h "$root/core/"
flags=(--target=avr -mmcu=atmega328p -Os -ffunction-sections -fdata-sections -w
       -DF_CPU=16000000L -DARDUINO=10607 -DARDUINO_AVR_UNO -DARDUINO_ARCH_AVR
       '-D__ATTR_PROGMEM__=__attribute__((__section__(".progmem.data")))'  # clang ignores __progmem__
       -nostdlibinc -isystem "$root/include" -I"$avr/cores/arduino" -I"$avr/variants/standard")
cxx=(-std=gnu++11 -fno-exceptions -fno-threadsafe-statics -fno-rtti)

compile() { # source, object, extra flags...
  local src=$1 obj=$2; shift 2
  case "$src" in
    *.c) "$bin/clang" "${flags[@]}" "$@" -std=gnu11 -c "$src" -o "$obj" ;;
    *.cpp) "$bin/clang" "${flags[@]}" "$@" "${cxx[@]}" -c "$src" -o "$obj" ;;
    *.S) "$bin/clang" "${flags[@]}" "$@" -x assembler-with-cpp -c "$src" -o "$obj" ;;
  esac
}

mkdir -p "$work/core"
for src in "$avr"/cores/arduino/*.{c,cpp,S}; do compile "$src" "$work/core/$(basename "$src").o"; done
"$bin/llvm-ar" rcs "$root/lib/core.a" "$work"/core/*.o

# libraries: headers under libraries/<Name>/, code in lib/lib<Name>.a
library() { # name, source dir
  local name=$1 src=$2 objs=()
  mkdir -p "$root/libraries/$name" "$work/lib-$name"
  (cd "$src" && find . -name '*.h' | while read -r h; do mkdir -p "$root/libraries/$name/$(dirname "$h")"; cp "$h" "$root/libraries/$name/$h"; done)
  for f in "$src"/*.c "$src"/*.cpp "$src"/utility/*.c "$src"/utility/*.cpp "$src"/avr/*.cpp; do
    [[ -e "$f" ]] || continue
    obj="$work/lib-$name/$(basename "$f").o"
    compile "$f" "$obj" -I"$src" -I"$src/utility"
    objs+=("$obj")
  done
  if ((${#objs[@]})); then "$bin/llvm-ar" rcs "$root/lib/lib$name.a" "${objs[@]}"; fi
}
for name in SPI Wire EEPROM SoftwareSerial; do library "$name" "$avr/libraries/$name/src"; done
library Servo "$servo"
library LiquidCrystal "$lcd"

mkdir -p "$out"
(cd "$root" && tar --format=ustar -cf "$out/sysroot.tar" .)
ls -la "$out/sysroot.tar"
