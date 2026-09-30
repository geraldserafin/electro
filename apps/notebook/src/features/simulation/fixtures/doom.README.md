# fixtures/doom.bin

Doom for a Raspberry Pi Pico with a 320×240 ILI9341 on SPI, as the "Nowe elementy" example wires it — for
tft.test.ts (the whole chain: the cores, DMA, SPI, the display). The notebook does not ship it: a user downloads
it from [geraldserafin/electro-doom](https://github.com/geraldserafin/electro-doom) (or builds it there: `build.sh`, which
says how and from what) and loads the file onto the board.

- the program: [kilograham/rp2040-doom](https://github.com/kilograham/rp2040-doom) (derived from Chocolate
  Doom: GNU GPL v2; its RP2040 code BSD-3), with the display files of
  [pondahai/rp2040-doom-ili9341](https://github.com/pondahai/rp2040-doom-ili9341) and electro-doom's
  `pico-doom.patch` — together its complete source, per the GPL;
- at 0x46000, `doom1.whx` from rp2040-doom: the shareware DOOM1.WAD (© id Software), compressed for it. id
  lets the shareware version be given away unchanged; this is a re-encoding of it, as rp2040-doom publishes it.
