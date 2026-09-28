#!/usr/bin/env bash
# Turns clang+lld built as WebAssembly (one WASI program, "llvm": see build-llvm-wasm.sh) into what
# the page loads (src/features/simulation/compiler/worker.ts), in public/arduino/:
#
#   llvm.js, llvm.core*.wasm   the program as a WebAssembly component, transpiled by jco for YoWASP's runtime
#   llvm.json                  which .wasm files there are
#   clang-headers.tar          clang's own headers (stddef.h, stdint.h, …): its resource dir is /usr
#
# Usage: make-arduino-compiler.sh <llvm-build dir>   (the sysroot comes from make-arduino-sysroot.sh)
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
build=$(cd "$1" && pwd)
out="$here/../public/arduino"
jco="$here/../node_modules/.bin/jco"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$out"
rm -f "$out"/llvm.js "$out"/llvm.core*.wasm

"$jco" new "$build/bin/llvm" --wasi-command --output "$work/llvm.wasm"
"$jco" transpile "$work/llvm.wasm" --instantiation async --no-typescript --no-namespaced-exports \
  --map 'wasi:io/*=runtime#io' --map 'wasi:cli/*=runtime#cli' --map 'wasi:clocks/*=runtime#*' \
  --map 'wasi:filesystem/*=runtime#fs' --map 'wasi:random/*=runtime#random' --out-dir "$work/gen"
cp "$work/gen/llvm.js" "$work"/gen/*.wasm "$out/"
(cd "$out" && ls llvm.core*.wasm) | node -e '
  const modules = require("fs").readFileSync(0, "utf8").trim().split("\n");
  require("fs").writeFileSync(process.argv[1], JSON.stringify({ modules }) + "\n");' "$out/llvm.json"

# only the freestanding C headers: the rest (CUDA, OpenCL, x86/ARM intrinsics, …) is of no use on an AVR
headers=$(find "$build" -type d -path '*/include' -exec test -f '{}/stddef.h' \; -print | head -1)
mkdir -p "$work/clang/include"
for h in stddef.h stdarg.h stdbool.h stdint.h inttypes.h float.h limits.h stdalign.h stdnoreturn.h stdatomic.h \
         iso646.h varargs.h stdckdint.h __stddef_*.h __stdarg_*.h __float_header_macro.h; do
  for f in "$headers"/$h; do [ -e "$f" ] && cp "$f" "$work/clang/include/"; done
done
(cd "$work/clang" && tar --format=ustar -cf "$out/clang-headers.tar" include)
ls -la "$out"
