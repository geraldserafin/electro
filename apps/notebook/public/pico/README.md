# public/pico

Flash images a Pico in the notebook can run whole, named by its program's first line
(`// firmware: /pico/doom.bin`; see src/features/simulation/firmware.ts).

## doom.bin

Doom for a Raspberry Pi Pico with a 320×240 ILI9341 on SPI, as the "Nowe elementy" example wires it; built by
`scripts/make-pico-doom.sh`, which says how and from what. In short:

- the program: [kilograham/rp2040-doom](https://github.com/kilograham/rp2040-doom) (derived from Chocolate
  Doom: GNU GPL v2; its RP2040 code BSD-3), with the display files of
  [pondahai/rp2040-doom-ili9341](https://github.com/pondahai/rp2040-doom-ili9341) and our
  `scripts/pico-doom.patch` — together its complete source, per the GPL;
- at 0x46000, `doom1.whx` from rp2040-doom: the shareware DOOM1.WAD (© id Software), compressed for it. id
  lets the shareware version be given away unchanged; this is a re-encoding of it — fine to use here, but
  think twice before publishing it.
