#!/usr/bin/env bash
# Builds public/pico/doom.bin: Doom for a Raspberry Pi Pico with a 320×240 ILI9341 on SPI, as the
# notebook's "Nowe elementy" example runs it — a whole flash image, the program and, at 0x46000, the
# shareware DOOM1.WAD compressed for it (doom1.whx).
#
# The program is kilograham/rp2040-doom (Chocolate Doom made to fit an RP2040: GPLv2, its own code
# BSD-3), with pondahai/rp2040-doom-ili9341's files over it (the LCD instead of VGA, eight buttons on
# GP2–GP9 and GP28), and pico-doom.patch over those — ours, for the emulator:
#   - EMU_LCD: no scanvideo (its PIO and DMA would scan a VGA picture out, the costliest thing to
#     emulate): a timer on core 1 sends a frame when one is rendered, a scanline at a time by DMA to SPI —
#     35 a second, the game's tics (the renderer renders a frame for each one that goes out);
#     the screen cleared in one transaction (not CS toggled for each pixel: each toggle a circuit event);
#   - no sound, no music (I²S by PIO, likewise);
#   - no melt between screens (its frames would come too slowly, and the game waits for it to end);
#   - waiting on core 1's and the display's semaphores asleep (WFE), not in a loop;
#   - the build: ILI9341, stand-alone (no loader), no Windows paths.
# Wiring (magc.h, src/pico/CMakeLists.txt): LCD SCK GP18, MOSI GP19, CS GP17, DC GP20, RESET GP21,
# backlight GP22; buttons to GND (pulled up): up GP9, down GP5, left GP8, right GP6, fire/B GP3,
# use/A GP2, start (enter) GP4, select (escape) GP28.
#
# Needs git, nix (for arm-none-eabi-gcc 13, cmake, make, clang for the SDK's host tools). Run from anywhere.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
out="$here/../public/pico/doom.bin"
work=$(mktemp -d)
[ -n "${KEEP:-}" ] && echo "keeping $work" || trap 'rm -rf "$work"' EXIT # (KEEP=1: to look into the build)

DOOM=29a453c980918a03e40fc8b69b024e7a3bdb5dc2   # kilograham/rp2040-doom
LCD=9f17b9f25ba0a886ce5db327e8a73f3949806065    # pondahai/rp2040-doom-ili9341
WAD_AT=$((0x46000))                              # TINY_WAD_ADDR − the flash's start

fetch() { # repo, commit, dir
  git init -q "$3" && git -C "$3" fetch -q --depth 1 "https://github.com/$1" "$2" && git -C "$3" checkout -q FETCH_HEAD
}
fetch kilograham/rp2040-doom $DOOM "$work/doom"
fetch pondahai/rp2040-doom-ili9341 $LCD "$work/lcd"
cp -R "$work/lcd/software/." "$work/doom/"
(cd "$work/doom" && patch -s -p1 < "$here/pico-doom.patch")
git clone -q --depth 1 -b 1.5.1 https://github.com/raspberrypi/pico-sdk "$work/pico-sdk"
git -C "$work/pico-sdk" submodule update -q --init --depth 1 lib/tinyusb # (the build takes its USB code even unused)
git clone -q --depth 1 -b sdk-1.5.1 https://github.com/raspberrypi/pico-extras "$work/pico-extras"

nix shell nixpkgs#gcc-arm-embedded-13 nixpkgs#cmake nixpkgs#gnumake nixpkgs#clang nixpkgs#python3 -c bash -c "
  set -e
  export CMAKE_POLICY_VERSION_MINIMUM=3.5 CC=clang CXX=clang++ # (the SDK's host tools: pioasm, elf2uf2)
  cmake -S '$work/doom' -B '$work/build' -DCMAKE_BUILD_TYPE=MinSizeRel -DPICO_BOARD=pico \
    -DPICO_SDK_PATH='$work/pico-sdk' -DPICO_EXTRAS_PATH='$work/pico-extras' > /dev/null
  make -C '$work/build' -j8 doom_tiny > /dev/null
"
bin="$work/build/src/doom_tiny.bin"
size=$(wc -c < "$bin")
[ "$size" -le $WAD_AT ] || { echo "the program ($size bytes) runs into the WAD at $WAD_AT" >&2; exit 1; }
mkdir -p "$(dirname "$out")"
{ cat "$bin"; head -c $((WAD_AT - size)) /dev/zero | LC_ALL=C tr '\0' '\377'; cat "$work/doom/doom1.whx"; } > "$out"
echo "$out: $(wc -c < "$out") bytes (the program $size)"
