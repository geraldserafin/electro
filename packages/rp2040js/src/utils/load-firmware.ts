// (ours) Loading a firmware file by its path is Node's (fs, and the uf2 package): the notebook puts the
// image in the flash itself. This keeps what the chips import from it, and says so if it is called.
import { IRPChip } from '../rpchip';

export interface LoadFirmwareOptions {
  reset?: boolean;
}

export interface LoadFirmwareResult {
  format: 'hex' | 'uf2';
}

export function loadFirmware<ChipType extends IRPChip = IRPChip>(
  _chip: ChipType,
  path: string,
  _options: LoadFirmwareOptions = {}
): LoadFirmwareResult {
  throw new Error(`loading ${path}: set the flash instead (no file system here)`);
}
