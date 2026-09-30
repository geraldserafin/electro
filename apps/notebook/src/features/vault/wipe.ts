// The vault in this browser (IndexedDB, through LightningFS) wiped: every note, the git history.
import LightningFS from "@isomorphic-git/lightning-fs";

export const FS_NAME = "electro";

export async function wipe() {
  const fs = new LightningFS(FS_NAME, { wipe: true });
  await fs.promises.readdir("/").catch(() => {}); // (the wipe happens on first use)
}
