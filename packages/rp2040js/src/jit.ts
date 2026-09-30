// (ours) A block translator for a Cortex-M0+ core: the Thumb code from an address up to the next
// branch taken (a "block": on past a conditional one not taken, along a B forward) becomes one
// JavaScript function — each instruction the interpreter's own statements (cortex-m0-core.ts), with its
// registers, immediates and the PC written in — which V8 then compiles to machine code. What the
// interpreter decodes every time it runs an instruction is done once; a loop of Doom's that branches back
// to its block's start goes round inside the function, its registers in locals.
//
// It keeps the interpreter's semantics to the bit: the same flags, the same cycles, memory through the
// same chip functions (with the RAM and the flash read in place). Interrupts are taken between blocks;
// a block ends early when an access to a peripheral makes one pending (as the core would take it after
// that instruction). Instructions it does not translate (WFE, WFI, MSR, MRS, SVC, BKPT, UDF) end a
// block, and the interpreter runs them. Code in RAM is translated too: a write to a RAM page with
// translated code in it forgets the blocks there.
import type { CortexM0Core } from './cortex-m0-core';
import type { RP2040 } from './rp2040';

const RAM = 0x20000000;
const RAM_SIZE = 264 * 1024;
const FLASH = 0x10000000;
const MAX_INSTRUCTIONS = 48;
const VERIFY_LOOPING = 200; // cycles a block that loops may go on for, checked (verify())
const PAGE = 8; // log2 of a RAM page's size (as rp2040.ts's codePages has it)

// a block: run once, or — a loop that branches back to its start — again while the core's cycles are below ``limit``
type Block = (limit: number) => void;

/** One instruction translated: its statements, its cycles (fixed part), whether the block ends with it. */
interface Translation {
  code: string;
  cycles: number;
  ends: boolean;
  exits?: boolean; // it may leave the block early (its statements contain an exit)
  jump?: number; // a branch the block follows: its next instruction is there
}

const hex = (n: number) => `0x${(n >>> 0).toString(16)}`;

/** The condition of a Bcond, on the core's flags (CortexM0Core.checkCondition). */
function condition(cond: number): string {
  const base = ['core.Z', 'core.C', 'core.N', 'core.V', '(core.C && !core.Z)', '(core.N === core.V)',
    '(core.N === core.V && !core.Z)', 'true'][cond >> 1];
  return cond & 1 && cond !== 0b1111 ? `!${base}` : base;
}

export class BlockJit {
  // where the block at an address is: an index into blocks (0: not translated yet, −1: not translatable),
  // by (pc − start) / 2 for the flash's first 2 MB and the RAM; elsewhere (the bootrom) a map
  private readonly blocks: Block[] = [() => {}];
  private readonly flashIndex = new Int32Array(1 << 20);
  private readonly ramIndex = new Int32Array(RAM_SIZE >> 1);
  private readonly otherBlocks = new Map<number, Block | null>();
  private readonly pageBlocks = new Map<number, number[]>(); // a RAM page → the RAM blocks' starts in it
  private readonly env: Record<string, unknown>;
  private readonly bit: number;
  private readonly recorder: { start(): void; stop(): { writes: number[]; slow: boolean } };
  private readonly lengths = new Map<Block, number>(); // each block's instructions (for verify())
  private lastEnd = 0; // where the block last translated ends
  /** Check every block against the interpreter (slow: for tests); the first difference, if any. */
  verifying = false;
  mismatch: string | null = null;
  /** Blocks translated, and runs of blocks, and instructions left to the interpreter (for a test's numbers). */
  readonly stats = { translated: 0, blocks: 0, interpreted: 0, forgotten: 0 };

  constructor(readonly core: CortexM0Core) {
    const chip = core.rpchip as RP2040;
    const ram = chip.sramView, ramBytes = chip.sram, flash = chip.flashView, flashBytes = chip.flash;
    const pages = chip.codePages;
    const sio = chip.sio;
    const FLASH_SIZE = flashBytes.length;
    const bit = 1 << core.coreNumber; // this core's bit in chip.codePages
    // verifying (verify()): the RAM words written, with what they held, and whether anything went past RAM and flash
    let recording: number[] | null = null;
    let slow = false;
    const record = (o: number) => {
      for (const w of [o & ~3, (o + 3) & ~3]) if (w < RAM_SIZE) recording!.push(w, ram.getUint32(w, true));
    };
    this.recorder = {
      start: () => { recording = []; slow = false; },
      stop: () => { const r = recording!; recording = null; return { writes: r, slow }; },
    };
    // the chip's memory functions, with the RAM and the flash in place (as rp2040.ts reads them)
    const r32 = (a: number) => {
      a >>>= 0;
      const o = a - RAM;
      if (o >= 0 && o < RAM_SIZE && !(a & 3)) return ram.getUint32(o, true);
      if (a >= FLASH && a < 0x14000000 && !(a & 3)) return flash.getUint32(a & 0xffffff, true);
      slow = true;
      if (a >= 0xd0000000 && a < 0xe0000000 && !(a & 3)) return sio.readUint32(a - 0xd0000000, chip.currentCore); // (the SIO: the interpolators, the divider)
      return chip.readUint32(a);
    };
    const r16 = (a: number) => {
      const o = a - RAM;
      if (o >= 0 && o < RAM_SIZE) return ram.getUint16(o, true);
      if (a >= FLASH && a < FLASH + FLASH_SIZE) return flash.getUint16(a - FLASH, true);
      slow = true;
      return chip.readUint16(a);
    };
    const r8 = (a: number) => {
      const o = a - RAM;
      if (o >= 0 && o < RAM_SIZE) return ramBytes[o];
      if (a >= FLASH && a < FLASH + FLASH_SIZE) return flashBytes[a - FLASH];
      slow = true;
      return chip.readUint8(a);
    };
    const w32 = (a: number, v: number) => {
      a >>>= 0;
      const o = a - RAM;
      if (o >= 0 && o < RAM_SIZE) {
        if (recording) record(o);
        ram.setUint32(o, v, true);
        if (pages[o >>> PAGE]) chip.onCodeWrite(o);
        return;
      }
      slow = true;
      if (a >= 0xd0000000 && a < 0xe0000000) {
        sio.writeUint32(a - 0xd0000000, v, chip.currentCore);
        return;
      }
      chip.writeUint32(a, v);
    };
    const w16 = (a: number, v: number) => {
      const o = a - RAM;
      if (o >= 0 && o < RAM_SIZE) {
        if (recording) record(o);
        ram.setUint16(o, v, true);
        if (pages[o >>> PAGE]) chip.onCodeWrite(o);
        return;
      }
      slow = true;
      chip.writeUint16(a, v);
    };
    const w8 = (a: number, v: number) => {
      const o = a - RAM;
      if (o >= 0 && o < RAM_SIZE) {
        if (recording) record(o);
        ramBytes[o] = v;
        if (pages[o >>> PAGE]) chip.onCodeWrite(o);
        return;
      }
      slow = true;
      chip.writeUint8(a, v);
    };
    // CortexM0Core.cyclesIO
    const io = (a: number) => {
      a >>>= 0;
      return a >= 0xd0000000 && a < 0xe0000000 ? 0 : a >= 0x40000000 && a < 0x50000000 ? 3 : 1;
    };
    const iow = (a: number) => {
      a >>>= 0;
      return a >= 0xd0000000 && a < 0xe0000000 ? 0 : a >= 0x40000000 && a < 0x50000000 ? 4 : 1;
    };
    this.env = { core, r32, r16, r8, w32, w16, w8, io, iow };
    this.bit = bit;
    const previous = chip.onCodeWrite;
    chip.onCodeWrite = (offset: number) => {
      previous(offset);
      this.forgetPage(offset >>> PAGE);
    };
  }

  /** Run a block (or one instruction, where there is no block): what executeInstruction does, more at once. */
  step(): void {
    const core = this.core;
    if (core.waiting) {
      core.cycles++;
      return;
    }
    // an exception taken: that is this step (the flag stays set, so the next one looks again — a higher one may
    // be pending too — and only then, with nothing left, runs a block)
    if (core.interruptsUpdated && core.checkForInterrupts()) {
      core.waiting = false;
      return;
    }
    const pc = core.registers[15] & ~1;
    const block = this.lookup(pc);
    if (block) {
      this.stats.blocks++;
      if (this.verifying) this.verify(block, pc);
      else block(0);
    } else {
      this.stats.interpreted++;
      core.executeInstruction();
    }
  }

  /**
   * Blocks (step()s) until the core's cycles reach ``limit`` or it waits (WFE, WFI): what as many step()s
   * do, with less between the blocks — a loop of a few instructions costs little more than its code.
   */
  run(limit: number): void {
    const core = this.core, flashIndex = this.flashIndex, blocks = this.blocks;
    if (this.verifying) {
      while (core.cycles < limit && !core.waiting) this.step();
      return;
    }
    while (core.cycles < limit && !core.waiting) {
      if (core.interruptsUpdated && core.checkForInterrupts()) { // (as in step())
        core.waiting = false;
        continue;
      }
      const pc = core.registers[15] & ~1;
      const f = (pc - FLASH) >>> 1;
      const k = f < flashIndex.length ? flashIndex[f] : 0;
      if (k > 0) {
        blocks[k](limit);
        continue;
      }
      const block = this.lookup(pc);
      if (block) block(limit);
      else {
        this.stats.interpreted++;
        core.executeInstruction();
      }
    }
  }

  /**
   * The block run, then undone (the core's state, the RAM it wrote) and its instructions run by the
   * interpreter instead: the two must agree. Blocks that touched a peripheral are not checked (what they
   * did there cannot be undone) — they keep what they did.
   */
  private verify(block: Block, pc: number) {
    const core = this.core, R = core.registers, chip = core.rpchip as RP2040, ram = chip.sramView;
    // (the PC without its bit 0: the interpreter carries the Thumb bit of a vector along, a block writes the address)
    const state = () => [...R.slice(0, 15), R[15] & ~1, core.N, core.Z, core.C, core.V, core.PM, core.cycles, core.waiting, core.interruptsUpdated].join(',');
    const before = { R: R.slice(), N: core.N, Z: core.Z, C: core.C, V: core.V, PM: core.PM, cycles: core.cycles };
    const mode = [core.currentMode, core.IPSR, core.SPSEL, core.bankedSP].join();
    this.recorder.start();
    block(core.cycles + VERIFY_LOOPING); // (a loop's block going round a few times: the interpreter as many)
    const { writes, slow } = this.recorder.stop();
    // (nor those that returned from an exception: the mode, the stacks cannot be put back as simply)
    if (slow || this.mismatch || [core.currentMode, core.IPSR, core.SPSEL, core.bankedSP].join() !== mode) return;
    const jitState = state(), cycles = core.cycles;
    const jitWords = new Map<number, number>();
    for (let i = 0; i < writes.length; i += 2) jitWords.set(writes[i], ram.getUint32(writes[i], true));
    for (let i = writes.length - 2; i >= 0; i -= 2) ram.setUint32(writes[i], writes[i + 1], true);
    R.set(before.R);
    Object.assign(core, { N: before.N, Z: before.Z, C: before.C, V: before.V, PM: before.PM, cycles: before.cycles });
    const n = this.lengths.get(block)!;
    while (core.cycles < cycles) core.executeInstruction(); // (as many instructions as took the block its cycles)
    const interpreted = state();
    const words: string[] = [];
    for (const [w, v] of jitWords) if (ram.getUint32(w, true) !== v) words.push(`${hex(RAM + w)}: jit ${hex(v)} interpreter ${hex(ram.getUint32(w, true))}`);
    if (jitState !== interpreted || words.length) {
      const names = ['r0', 'r1', 'r2', 'r3', 'r4', 'r5', 'r6', 'r7', 'r8', 'r9', 'r10', 'r11', 'r12', 'sp', 'lr', 'pc', 'N', 'Z', 'C', 'V', 'PM', 'cycles', 'waiting', 'interruptsUpdated'];
      const a = jitState.split(','), b = interpreted.split(',');
      const diff = names.flatMap((name, i) => (a[i] !== b[i] ? [`${name}: jit ${a[i]} interpreter ${b[i]}`] : []));
      this.mismatch = `block at ${hex(pc)} (${n} instructions): ${[...diff, ...words].join('; ')}`;
    }
  }

  private lookup(pc: number): Block | null {
    let block: Block | null | undefined;
    const f = (pc - FLASH) >>> 1, m = (pc - RAM) >>> 1;
    if (f < this.flashIndex.length) {
      const k = this.flashIndex[f];
      if (k > 0) return this.blocks[k];
      if (k < 0) return null;
      block = this.translate(pc);
      this.flashIndex[f] = this.keep(block);
    } else if (m < this.ramIndex.length) {
      const k = this.ramIndex[m];
      if (k > 0) return this.blocks[k];
      if (k < 0) return null;
      block = this.translate(pc);
      this.ramIndex[m] = this.keep(block);
      if (block) this.markRam(pc, this.lastEnd);
    } else {
      block = this.otherBlocks.get(pc);
      if (block === undefined) {
        block = this.translate(pc);
        this.otherBlocks.set(pc, block);
      }
    }
    return block;
  }

  private keep(block: Block | null): number {
    if (!block) return -1;
    this.blocks.push(block);
    return this.blocks.length - 1;
  }

  /** A RAM block's pages (as far as a block can reach) marked: a write there forgets it. */
  private markRam(pc: number, end: number) {
    const chip = this.core.rpchip as RP2040;
    const first = (pc - RAM) >>> PAGE, last = Math.min((end - 1 - RAM) >>> PAGE, chip.codePages.length - 1);
    for (let p = first; p <= last; p++) {
      chip.codePages[p] |= this.bit;
      let starts = this.pageBlocks.get(p);
      if (!starts) this.pageBlocks.set(p, (starts = []));
      starts.push(pc);
    }
  }

  private forgetPage(page: number) {
    const starts = this.pageBlocks.get(page);
    if (!starts) return;
    for (const pc of starts) {
      this.ramIndex[(pc - RAM) >>> 1] = 0; // (its function left in blocks: forgotten blocks are few)
      this.stats.forgotten++;
    }
    this.pageBlocks.delete(page);
    (this.core.rpchip as RP2040).codePages[page] &= ~this.bit;
  }

  private translate(start: number): Block | null {
    const core = this.core;
    const lines: string[] = [];
    let pc = start, cycles = 0, count = 0, ended = false;
    while (count < MAX_INSTRUCTIONS) {
      const opcode = core.readUint16(pc);
      const wide = opcode >> 12 === 0b1111 || opcode >> 11 === 0b11101;
      const opcode2 = wide ? core.readUint16(pc + 2) : 0;
      const t = translateOne(opcode, opcode2, pc, cycles, (a) => core.readUint16(a), start);
      if (!t) break; // (left to the interpreter: the block ends before it)
      lines.push(t.code);
      cycles += t.cycles;
      count++;
      pc = t.jump ?? pc + (wide ? 4 : 2);
      if (t.ends) {
        ended = true;
        break;
      }
    }
    if (!count) return null;
    this.lastEnd = pc;
    if (!ended) lines.push(`R[15] = ${hex(pc)};`);
    const source = `return function block_${start.toString(16)}(limit) {\n${localize(lines, cycles)}\n};`;
    const env = this.env;
    // eslint-disable-next-line @typescript-eslint/no-implied-eval
    const make = new Function(...Object.keys(env), source) as (...args: unknown[]) => Block;
    this.stats.translated++;
    const block = make(...Object.values(env));
    this.lengths.set(block, count);
    return block;
  }
}

/**
 * The block's statements with its registers and flags in locals (q0–q15: not r8, r16, the memory functions' names): read from the core at the start, written
 * back where it leaves (the exits, the end) and before a call that looks at the core (BXWritePC, blTaken:
 * after those the block ends). A register's value as the core keeps it: 32 bits, unsigned. A block that
 * branches back to its start is a loop (its branch continues it): the registers stay in the locals.
 */
function localize(lines: string[], cycles: number): string {
  let body = lines.join('\n');
  const assigned = new Set<number>(), used = new Set<number>();
  body = body.replace(/R\[(\d+)\] = ([^;]+);/g, (_, n: string, e: string) => {
    assigned.add(+n);
    return `q${n} = (${e}) >>> 0;`;
  });
  body = body.replace(/R\[(\d+)\]/g, (_, n: string) => {
    used.add(+n);
    return `q${n}`;
  });
  for (const n of assigned) used.add(n);
  const flagsRead = /core\.[NZCV]\b/.test(body), flagsSet = /core\.[NZCV] = /.test(body);
  body = body.replace(/core\.([NZCV])\b/g, '$1');
  const back = [...assigned].map((n) => `R[${n}] = q${n};`).join(' ') + (flagsSet ? ' core.N = N; core.Z = Z; core.C = C; core.V = V;' : '');
  const calls = /core\.(BXWritePC|blTaken)\(/.test(lines[lines.length - 1]) || /core\.(BXWritePC|blTaken)\(/.test(lines[lines.length - 2] ?? '');
  body = body.replace(/return;/g, `${back} return;`).replace(/core\.(BXWritePC|blTaken)\(/g, `${back} core.$1(`);
  if (body.includes('continue;')) body = `for (;;) {\n${body}\nbreak;\n}`;
  const head = ['const R = core.registers; let x, y, res, a;'];
  if (used.size) head.push(`let ${[...used].map((n) => `q${n} = R[${n}]`).join(', ')};`);
  if (flagsRead) head.push('let N = core.N, Z = core.Z, C = core.C, V = core.V;');
  return `${head.join('\n')}\n${body}\n${calls ? '' : back} core.cycles += ${cycles};`;
}

/** A register as an instruction reads it: R[n], and for the PC the address of the instruction + 2 (the interpreter's). */
const reg = (n: number, pc: number) => (n === 15 ? hex(pc + 2) : `R[${n}]`);

const nz = (v: string) => `core.N = !!(${v} & 0x80000000); core.Z = (${v} & 0xffffffff) === 0;`;
const nz0 = (v: string) => `core.N = !!(${v} & 0x80000000); core.Z = ${v} === 0;`;
// CortexM0Core.addUpdateFlags / substractUpdateFlags, on x and y; the result in res
const add = (a: string, b: string) =>
  `x = ${a}; y = ${b}; res = (x + y) >>> 0; core.N = !!(res & 0x80000000); core.Z = res === 0; ` +
  `core.C = x >>> 0 > 0xffffffff - (y >>> 0); core.V = (~(x ^ y) & (x ^ res)) < 0;`;
const sub = (a: string, b: string) =>
  `x = ${a}; y = ${b}; res = (x - y) >>> 0; core.N = !!(res & 0x80000000); core.Z = res === 0; ` +
  `core.C = x >= y; core.V = ((x ^ y) & (x ^ res)) < 0;`;

/**
 * One instruction's statements, the interpreter's (cortex-m0-core.ts: the same tests, in the same order);
 * ``before``: the block's cycles before it (for an exit's count). Null: not translated.
 */
function translateOne(opcode: number, opcode2: number, pc: number, before: number, read16: (a: number) => number, start: number): Translation | null {
  const next = pc + 2;
  const r = (n: number) => reg(n, pc);
  // leaving the block after this instruction (its fixed cycles ``c`` counted), at ``to``
  const exit = (to: string, c: number) => `{ R[15] = ${to}; core.cycles += ${before + c}; return; }`;
  // a branch back to the block's start: round again (the block is a loop, see localize) while there is time
  const again = (to: number, c: number) => `{ core.cycles += ${before + c}; if (core.cycles < limit) continue; R[15] = ${hex(to)}; return; }`;
  // an access that went to a peripheral may have made an interrupt pending: then the core takes it now
  const checked = (code: string, c: number, after = next) =>
    ({ code: `${code}\nif (core.interruptsUpdated) ${exit(hex(after), c)}`, cycles: c, ends: false, exits: true });
  const op = (code: string, c = 1): Translation => ({ code, cycles: c, ends: false });

  // ADCS
  if (opcode >> 6 === 0b0100000101) {
    const Rm = (opcode >> 3) & 7, Rdn = opcode & 7;
    return op(`${add(r(Rm), `${r(Rdn)} + (core.C ? 1 : 0)`)} R[${Rdn}] = res;`);
  }
  // ADD (register = SP plus immediate)
  if (opcode >> 11 === 0b10101) {
    const imm8 = opcode & 0xff, Rd = (opcode >> 8) & 7;
    return op(`R[${Rd}] = R[13] + ${imm8 << 2};`);
  }
  // ADD (SP plus immediate)
  if (opcode >> 7 === 0b101100000) return op(`R[13] = (R[13] + ${(opcode & 0x7f) << 2}) & ~0x3;`);
  // ADDS (Encoding T1)
  if (opcode >> 9 === 0b0001110) {
    const imm3 = (opcode >> 6) & 7, Rn = (opcode >> 3) & 7, Rd = opcode & 7;
    return op(`${add(r(Rn), `${imm3}`)} R[${Rd}] = res;`);
  }
  // ADDS (Encoding T2)
  if (opcode >> 11 === 0b00110) {
    const imm8 = opcode & 0xff, Rdn = (opcode >> 8) & 7;
    return op(`${add(r(Rdn), `${imm8}`)} R[${Rdn}] = res;`);
  }
  // ADDS (register)
  if (opcode >> 9 === 0b0001100) {
    const Rm = (opcode >> 6) & 7, Rn = (opcode >> 3) & 7, Rd = opcode & 7;
    return op(`${add(r(Rn), r(Rm))} R[${Rd}] = res;`);
  }
  // ADD (register)
  if (opcode >> 8 === 0b01000100) {
    const Rm = (opcode >> 3) & 0xf, Rdn = ((opcode & 0x80) >> 4) | (opcode & 7);
    const left = Rdn === 15 ? hex(next + 2) : `R[${Rdn}]`;
    if (Rdn === 15) return { code: `R[15] = (${left} + ${r(Rm)}) & ~0x1;`, cycles: 2, ends: true };
    if (Rdn === 13) return op(`R[13] = (${left} + ${r(Rm)}) & ~0x3;`);
    return op(`R[${Rdn}] = ${left} + ${r(Rm)};`);
  }
  // ADR
  if (opcode >> 11 === 0b10100) {
    const imm8 = opcode & 0xff, Rd = (opcode >> 8) & 7;
    return op(`R[${Rd}] = ${hex((pc & 0xfffffffc) + 4 + (imm8 << 2))};`);
  }
  // ANDS (Encoding T2)
  if (opcode >> 6 === 0b0100000000) {
    const Rm = (opcode >> 3) & 7, Rdn = opcode & 7;
    return op(`res = ${r(Rdn)} & ${r(Rm)}; R[${Rdn}] = res; ${nz('res')}`);
  }
  // ASRS (immediate)
  if (opcode >> 11 === 0b00010) {
    const imm5 = (opcode >> 6) & 0x1f, Rm = (opcode >> 3) & 7, Rd = opcode & 7;
    const shiftN = imm5 ? imm5 : 32;
    const result = shiftN < 32 ? `x >> ${shiftN}` : `(x & 0x80000000) >> 31`;
    return op(`x = ${r(Rm)}; res = ${result}; R[${Rd}] = res; ${nz('res')} core.C = x & ${hex(1 << (shiftN - 1))} ? true : false;`);
  }
  // ASRS (register)
  if (opcode >> 6 === 0b0100000100) {
    const Rm = (opcode >> 3) & 7, Rdn = opcode & 7;
    return op(`x = ${r(Rdn)}; y = (${r(Rm)} & 0xff) < 32 ? ${r(Rm)} & 0xff : 32; ` +
      `res = y < 32 ? x >> y : (x & 0x80000000) >> 31; R[${Rdn}] = res; ${nz('res')} core.C = x & (1 << (y - 1)) ? true : false;`);
  }
  // B (with cond)
  if (opcode >> 12 === 0b1101 && ((opcode >> 9) & 7) !== 0b111) {
    let imm8 = (opcode & 0xff) << 1;
    const cond = (opcode >> 8) & 0xf;
    if (imm8 & (1 << 8)) imm8 = (imm8 & 0x1ff) - 0x200;
    const to = next + imm8 + 2;
    // (not taken, the block goes on)
    return { code: `if (${condition(cond)}) ${to === start ? again(to, 2) : exit(hex(to), 2)}`, cycles: 1, ends: false, exits: true };
  }
  // B
  if (opcode >> 11 === 0b11100) {
    let imm11 = (opcode & 0x7ff) << 1;
    if (imm11 & (1 << 11)) imm11 = (imm11 & 0x7ff) - 0x800;
    if (read16(pc + 2) === 0xabcd && read16(pc + 4) === 0xffff) return null; // (the profiler's trace marker: the interpreter's)
    const to = next + imm11 + 2;
    if (to === start) return { code: `${again(to, 2)}\nR[15] = ${hex(to)};`, cycles: 2, ends: true };
    if (to > pc) return { code: '', cycles: 2, ends: false, jump: to }; // (forward: the block goes on there)
    return { code: `R[15] = ${hex(to)};`, cycles: 2, ends: true };
  }
  // BICS
  if (opcode >> 6 === 0b0100001110) {
    const Rm = (opcode >> 3) & 7, Rdn = opcode & 7;
    return op(`R[${Rdn}] = R[${Rdn}] & ~${r(Rm)}; res = R[${Rdn}]; ${nz0('res')}`);
  }
  // BKPT
  if (opcode >> 8 === 0b10111110) return null;
  // BL
  if (opcode >> 11 === 0b11110 && opcode2 >> 14 === 0b11 && ((opcode2 >> 12) & 1) === 1) {
    const imm11 = opcode2 & 0x7ff, J2 = (opcode2 >> 11) & 1, J1 = (opcode2 >> 13) & 1;
    const imm10 = opcode & 0x3ff, S = (opcode >> 10) & 1;
    const I1 = 1 - (S ^ J1), I2 = 1 - (S ^ J2);
    const imm32 = ((S ? 0b11111111 : 0) << 24) | ((I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1));
    return { code: `R[14] = ${hex((next + 2) | 1)}; R[15] = ${hex(next + 2 + imm32)}; core.blTaken(core, false);`, cycles: 3, ends: true };
  }
  // BLX
  if (opcode >> 7 === 0b010001111 && (opcode & 7) === 0) {
    const Rm = (opcode >> 3) & 0xf;
    return { code: `x = ${r(Rm)}; R[14] = ${hex(next | 1)}; R[15] = x & ~1; core.blTaken(core, true);`, cycles: 2, ends: true };
  }
  // BX
  if (opcode >> 7 === 0b010001110 && (opcode & 7) === 0) {
    const Rm = (opcode >> 3) & 0xf;
    return { code: `R[15] = ${hex(next)}; core.BXWritePC(${r(Rm)});`, cycles: 2, ends: true };
  }
  // CMN (register)
  if (opcode >> 6 === 0b0100001011) return op(add(r(opcode & 7), r((opcode >> 3) & 7)));
  // CMP immediate
  if (opcode >> 11 === 0b00101) return op(sub(r((opcode >> 8) & 7), `${opcode & 0xff}`));
  // CMP (register)
  if (opcode >> 6 === 0b0100001010) return op(sub(r(opcode & 7), r((opcode >> 3) & 7)));
  // CMP (register) encoding T2
  if (opcode >> 8 === 0b01000101) {
    const Rm = (opcode >> 3) & 0xf, Rn = ((opcode >> 4) & 0x8) | (opcode & 7);
    return op(sub(r(Rn), r(Rm)));
  }
  // CPSID i
  if (opcode === 0xb672) return op('core.PM = true;');
  // CPSIE i: an interrupt may be taken now
  if (opcode === 0xb662) return { code: `core.PM = false; core.interruptsUpdated = true; R[15] = ${hex(next)};`, cycles: 1, ends: true };
  // DMB SY, DSB SY
  if (opcode === 0xf3bf && ((opcode2 & 0xfff0) === 0x8f50 || (opcode2 & 0xfff0) === 0x8f40)) return op('', 3);
  // EORS
  if (opcode >> 6 === 0b0100000001) {
    const Rm = (opcode >> 3) & 7, Rdn = opcode & 7;
    return op(`res = ${r(Rm)} ^ ${r(Rdn)}; R[${Rdn}] = res; ${nz0('res')}`);
  }
  // ISB SY
  if (opcode === 0xf3bf && (opcode2 & 0xfff0) === 0x8f60) return op('', 3);
  // LDMIA
  if (opcode >> 11 === 0b11001) {
    const Rn = (opcode >> 8) & 7, list = opcode & 0xff;
    const lines = [`a = ${r(Rn)};`];
    let c = 1;
    for (let i = 0; i < 8; i++) if (list & (1 << i)) { lines.push(`R[${i}] = r32(a); a += 4;`); c++; }
    if (!(list & (1 << Rn))) lines.push(`R[${Rn}] = a;`);
    return checked(lines.join(' '), c);
  }
  // loads: LDR (immediate), (sp + immediate), (literal), (register); LDRB, LDRH, LDRSB, LDRSH
  const load = (address: string, Rt: number, read: string) =>
    checked(`a = ${address}; core.cycles += io(a); R[${Rt}] = ${read};`, 1);
  if (opcode >> 11 === 0b01101) return load(`${r((opcode >> 3) & 7)} + ${((opcode >> 6) & 0x1f) << 2}`, opcode & 7, 'r32(a)');
  if (opcode >> 11 === 0b10011) return load(`R[13] + ${(opcode & 0xff) << 2}`, (opcode >> 8) & 7, 'r32(a)');
  if (opcode >> 11 === 0b01001) return load(hex(((next + 2) & 0xfffffffc) + ((opcode & 0xff) << 2)), (opcode >> 8) & 7, 'r32(a)');
  const rr = () => `${r((opcode >> 6) & 7)} + ${r((opcode >> 3) & 7)}`;
  if (opcode >> 9 === 0b0101100) return load(rr(), opcode & 7, 'r32(a)');
  if (opcode >> 11 === 0b01111) return load(`${r((opcode >> 3) & 7)} + ${(opcode >> 6) & 0x1f}`, opcode & 7, 'r8(a)');
  if (opcode >> 9 === 0b0101110) return load(rr(), opcode & 7, 'r8(a)');
  if (opcode >> 11 === 0b10001) return load(`${r((opcode >> 3) & 7)} + ${((opcode >> 6) & 0x1f) << 1}`, opcode & 7, 'r16(a)');
  if (opcode >> 9 === 0b0101101) return load(rr(), opcode & 7, 'r16(a)');
  if (opcode >> 9 === 0b0101011) return load(rr(), opcode & 7, '(r8(a) << 24) >> 24');
  if (opcode >> 9 === 0b0101111) return load(rr(), opcode & 7, '(r16(a) << 16) >> 16');
  // LSLS (immediate)
  if (opcode >> 11 === 0b00000) {
    const imm5 = (opcode >> 6) & 0x1f, Rm = (opcode >> 3) & 7, Rd = opcode & 7;
    const carry = imm5 ? `core.C = !!(x & ${hex(1 << (32 - imm5))});` : '';
    return op(`x = ${r(Rm)}; res = x << ${imm5}; R[${Rd}] = res; ${nz0('res')} ${carry}`);
  }
  // LSLS (register)
  if (opcode >> 6 === 0b0100000010) {
    const Rm = (opcode >> 3) & 7, Rdn = opcode & 7;
    return op(`x = ${r(Rdn)}; y = ${r(Rm)} & 0xff; res = y >= 32 ? 0 : x << y; R[${Rdn}] = res; ${nz0('res')} ` +
      `core.C = y ? !!(x & (1 << (32 - y))) : core.C;`);
  }
  // LSRS (immediate)
  if (opcode >> 11 === 0b00001) {
    const imm5 = (opcode >> 6) & 0x1f, Rm = (opcode >> 3) & 7, Rd = opcode & 7;
    return op(`x = ${r(Rm)}; res = ${imm5 ? `x >>> ${imm5}` : '0'}; R[${Rd}] = res; ${nz0('res')} ` +
      `core.C = !!((x >>> ${imm5 ? imm5 - 1 : 31}) & 0x1);`);
  }
  // LSRS (register)
  if (opcode >> 6 === 0b0100000011) {
    const Rm = (opcode >> 3) & 7, Rdn = opcode & 7;
    return op(`y = ${r(Rm)} & 0xff; x = ${r(Rdn)}; res = y < 32 ? x >>> y : 0; R[${Rdn}] = res; ${nz0('res')} ` +
      `core.C = y <= 32 ? !!((x >>> (y - 1)) & 0x1) : false;`);
  }
  // MOV
  if (opcode >> 8 === 0b01000110) {
    const Rm = (opcode >> 3) & 0xf, Rd = ((opcode >> 4) & 0x8) | (opcode & 7);
    const value = Rm === 15 ? hex(next + 2) : `R[${Rm}]`;
    if (Rd === 15) return { code: `R[15] = ${value} & ~1;`, cycles: 2, ends: true };
    if (Rd === 13) return op(`R[13] = ${value} & ~3;`);
    return op(`R[${Rd}] = ${value};`);
  }
  // MOVS
  if (opcode >> 11 === 0b00100) {
    const value = opcode & 0xff, Rd = (opcode >> 8) & 7;
    return op(`R[${Rd}] = ${value}; core.N = false; core.Z = ${value === 0};`);
  }
  // MRS, MSR
  if (opcode === 0b1111001111101111 && opcode2 >> 12 === 0b1000) return null;
  if (opcode >> 4 === 0b111100111000 && opcode2 >> 8 === 0b10001000) return null;
  // MULS
  if (opcode >> 6 === 0b0100001101) {
    const Rn = (opcode >> 3) & 7, Rdm = opcode & 7;
    return op(`res = Math.imul(${r(Rn)}, ${r(Rdm)}); R[${Rdm}] = res; ${nz('res')}`);
  }
  // MVNS
  if (opcode >> 6 === 0b0100001111) {
    const Rm = (opcode >> 3) & 7, Rd = opcode & 7;
    return op(`res = ~${r(Rm)}; R[${Rd}] = res; ${nz0('res')}`);
  }
  // ORRS (Encoding T2)
  if (opcode >> 6 === 0b0100001100) {
    const Rm = (opcode >> 3) & 7, Rdn = opcode & 7;
    return op(`res = ${r(Rdn)} | ${r(Rm)}; R[${Rdn}] = res; ${nz('res')}`);
  }
  // POP
  if (opcode >> 9 === 0b1011110) {
    const P = (opcode >> 8) & 1;
    const lines = ['a = R[13];'];
    let c = 1;
    for (let i = 0; i <= 7; i++) if (opcode & (1 << i)) { lines.push(`R[${i}] = r32(a); a += 4;`); c++; }
    if (P) {
      lines.push(`R[13] = (a + 4) & ~0x3; R[15] = ${hex(next)}; core.BXWritePC(r32(a));`);
      return { code: lines.join(' '), cycles: c + 2, ends: true };
    }
    lines.push('R[13] = a & ~0x3;');
    return checked(lines.join(' '), c);
  }
  // PUSH
  if (opcode >> 9 === 0b1011010) {
    let bitCount = 0;
    for (let i = 0; i <= 8; i++) if (opcode & (1 << i)) bitCount++;
    const lines = [`a = R[13] - ${4 * bitCount};`];
    let c = 1;
    for (let i = 0; i <= 7; i++) if (opcode & (1 << i)) { lines.push(`w32(a, R[${i}]); a += 4;`); c++; }
    if (opcode & (1 << 8)) lines.push('w32(a, R[14]);');
    lines.push(`R[13] = (R[13] - ${4 * bitCount}) & ~0x3;`);
    return checked(lines.join(' '), c);
  }
  // REV, REV16, REVSH
  if (opcode >> 6 === 0b1011101000) {
    const Rm = (opcode >> 3) & 7, Rd = opcode & 7;
    return op(`x = ${r(Rm)}; R[${Rd}] = ((x & 0xff) << 24) | (((x >> 8) & 0xff) << 16) | (((x >> 16) & 0xff) << 8) | ((x >> 24) & 0xff);`);
  }
  if (opcode >> 6 === 0b1011101001) {
    const Rm = (opcode >> 3) & 7, Rd = opcode & 7;
    return op(`x = ${r(Rm)}; R[${Rd}] = (((x >> 16) & 0xff) << 24) | (((x >> 24) & 0xff) << 16) | ((x & 0xff) << 8) | ((x >> 8) & 0xff);`);
  }
  if (opcode >> 6 === 0b1011101011) {
    const Rm = (opcode >> 3) & 7, Rd = opcode & 7;
    return op(`x = ${r(Rm)}; R[${Rd}] = ((((x & 0xff) << 8) | ((x >> 8) & 0xff)) << 16) >> 16;`);
  }
  // ROR
  if (opcode >> 6 === 0b0100000111) {
    const Rm = (opcode >> 3) & 7, Rdn = opcode & 7;
    return op(`x = ${r(Rdn)}; y = (${r(Rm)} & 0xff) % 32; res = (x >>> y) | (x << (32 - y)); R[${Rdn}] = res; ${nz0('res')} core.C = !!(res & 0x80000000);`);
  }
  // NEGS / RSBS
  if (opcode >> 6 === 0b0100001001) {
    const Rn = (opcode >> 3) & 7, Rd = opcode & 7;
    return op(`${sub('0', r(Rn))} R[${Rd}] = res;`);
  }
  // NOP
  if (opcode === 0b1011111100000000) return op('');
  // SBCS (Encoding T1)
  if (opcode >> 6 === 0b0100000110) {
    const Rm = (opcode >> 3) & 7, Rdn = opcode & 7;
    return op(`${sub(r(Rdn), `${r(Rm)} + (1 - (core.C ? 1 : 0))`)} R[${Rdn}] = res;`);
  }
  // SEV
  if (opcode === 0b1011111101000000) return op('core.fireSEV();');
  // STMIA
  if (opcode >> 11 === 0b11000) {
    const Rn = (opcode >> 8) & 7, list = opcode & 0xff;
    const lines = [`a = ${r(Rn)};`];
    let c = 1;
    for (let i = 0; i < 8; i++) if (list & (1 << i)) { lines.push(`w32(a, R[${i}]); a += 4;`); c++; }
    if (!(list & (1 << Rn))) lines.push(`R[${Rn}] = a;`);
    return checked(lines.join(' '), c);
  }
  // stores: STR (immediate), (sp + immediate), (register); STRB, STRH
  const store = (address: string, Rt: number, write: string) =>
    checked(`a = ${address}; core.cycles += iow(a); ${write}(a, R[${Rt}]);`, 1);
  if (opcode >> 11 === 0b01100) return store(`${r((opcode >> 3) & 7)} + ${((opcode >> 6) & 0x1f) << 2}`, opcode & 7, 'w32');
  if (opcode >> 11 === 0b10010) return store(`R[13] + ${(opcode & 0xff) << 2}`, (opcode >> 8) & 7, 'w32');
  if (opcode >> 9 === 0b0101000) return store(rr(), opcode & 7, 'w32');
  if (opcode >> 11 === 0b01110) return store(`${r((opcode >> 3) & 7)} + ${(opcode >> 6) & 0x1f}`, opcode & 7, 'w8');
  if (opcode >> 9 === 0b0101010) return store(rr(), opcode & 7, 'w8');
  if (opcode >> 11 === 0b10000) return store(`${r((opcode >> 3) & 7)} + ${((opcode >> 6) & 0x1f) << 1}`, opcode & 7, 'w16');
  if (opcode >> 9 === 0b0101001) return store(rr(), opcode & 7, 'w16');
  // SUB (SP minus immediate)
  if (opcode >> 7 === 0b101100001) return op(`R[13] = (R[13] - ${(opcode & 0x7f) << 2}) & ~0x3;`);
  // SUBS (Encoding T1), (Encoding T2), (register)
  if (opcode >> 9 === 0b0001111) {
    const imm3 = (opcode >> 6) & 7, Rn = (opcode >> 3) & 7, Rd = opcode & 7;
    return op(`${sub(r(Rn), `${imm3}`)} R[${Rd}] = res;`);
  }
  if (opcode >> 11 === 0b00111) {
    const imm8 = opcode & 0xff, Rdn = (opcode >> 8) & 7;
    return op(`${sub(r(Rdn), `${imm8}`)} R[${Rdn}] = res;`);
  }
  if (opcode >> 9 === 0b0001101) {
    const Rm = (opcode >> 6) & 7, Rn = (opcode >> 3) & 7, Rd = opcode & 7;
    return op(`${sub(r(Rn), r(Rm))} R[${Rd}] = res;`);
  }
  // SVC
  if (opcode >> 8 === 0b11011111) return null;
  // SXTB, SXTH
  if (opcode >> 6 === 0b1011001001) return op(`R[${opcode & 7}] = (${r((opcode >> 3) & 7)} << 24) >> 24;`);
  if (opcode >> 6 === 0b1011001000) return op(`R[${opcode & 7}] = (${r((opcode >> 3) & 7)} << 16) >> 16;`);
  // TST
  if (opcode >> 6 === 0b0100001000) return op(`res = ${r(opcode & 7)} & ${r((opcode >> 3) & 7)}; ${nz0('res')}`);
  // UDF, UDF (Encoding T2)
  if (opcode >> 8 === 0b11011110) return null;
  if (opcode >> 4 === 0b111101111111 && opcode2 >> 12 === 0b1010) return null;
  // UXTB, UXTH
  if (opcode >> 6 === 0b1011001011) return op(`R[${opcode & 7}] = ${r((opcode >> 3) & 7)} & 0xff;`);
  if (opcode >> 6 === 0b1011001010) return op(`R[${opcode & 7}] = ${r((opcode >> 3) & 7)} & 0xffff;`);
  // WFE, WFI, YIELD, and anything else: the interpreter's
  return null;
}

