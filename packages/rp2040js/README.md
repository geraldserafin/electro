# @electro/rp2040js

The RP2040 emulator the notebook runs a Raspberry Pi Pico on. `src/` is copied from
[c1570/rp2040js](https://github.com/c1570/rp2040js) at commit `af0114cbee8e9e91574204b66f10aa2961cbf28c`
(MIT, see LICENSE), itself a fork of [wokwi/rp2040js](https://github.com/wokwi/rp2040js). The fork adds what
upstream lacks and the notebook needs: the second core (with the SIO FIFOs, spinlocks, per-core
interrupts), SSI flash boot, DMA paced by SPI.

Only the files an `RP2040` imports are here (it takes some RP2350 code along, shared through the loader
and the bootroms). Ours, besides `src/index.ts`:

- the clock tree, from wokwi/rp2040js 1.4.0 (e99f918, cd0c222): `src/peripherals/pll.ts`,
  `src/peripherals/clocks_rp2040.ts` and `RP2040.updateClocks()` — clk_sys follows `set_sys_clock_khz()`
  (arduino-pico runs at 200 MHz, and its PWM and PIO dividers count on it), clk_peri is what the UARTs and
  SPIs divide;
- `src/utils/load-firmware.ts`: loading a file by its path needs Node — the notebook sets the flash itself;
- `src/peripherals/pio.ts`: its timer handle typed `ReturnType<typeof setTimeout>`, not `NodeJS.Timeout`;
- `src/jit.ts`: a block translator — the Thumb code up to a branch taken made one JavaScript function (a
  loop back to its start going round inside it), with the interpreter's semantics (checked against it in the
  notebook's jit.test.ts), more than ten times faster; `run(limit)` runs blocks up to a cycle count; for it,
  `RP2040.codePages` and `onCodeWrite` (a write to RAM with translated code in it forgets that code);
- for speed, the same behaviour: DMA transfers in bursts while the request stays up (`dma.ts`), an SPI's
  `sink` taking each byte at once, and a DMA's burst to it whole (`sinkBurst`, `sinkMany`; `RP2040.sinkAt`,
  `memoryAt`), the interpolators working on the control bits directly (`interpolator.ts`), `findPeripheral`
  on an array (`rp2040.ts`).

The code wants `useDefineForClassFields: false` (its field initializers use constructor parameters):
tsconfig.json has it, and Vite and esbuild read it from there; so does the notebook's, whose `tsc` checks it.
The npm package `rp2350js` is older than that commit and does not boot what the notebook runs. To update:
copy the same files from a newer commit, keep ours, and run the notebook's Pico tests.
