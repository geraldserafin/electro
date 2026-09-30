// A Pico's program from a file — a .uf2 as one drags onto a Pico in BOOTSEL mode, or a flash image
// (.bin): picked in the board's inspector, or dropped on the board (SchematicCell). The file goes to the
// notes server (kept by what is in it: @electro/notes-api's Firmware.ts) and the board's text names it on
// its first line (firmware.ts), so the note runs it wherever it is opened; on the chip at once meanwhile.
// Not saved (signed out, no server): it runs anyway, only for now.
import { useAtomSet } from "@effect-atom/atom-react";
import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import { FIRMWARE_MAX } from "@electro/notes-api";
import { failure } from "@/features/notes/sync";
import { uploadFirmware } from "./atoms";
import { firmwareUrl, flashOf, withFirmware } from "./firmware";
import type { Live } from "./useLive";

/** Whether a drag carries files (to drop on a board). */
export const carriesFiles = (e: React.DragEvent) => Array.from(e.dataTransfer.types).includes("Files");

/**
 * ``load(id, file)``: the file onto board ``id`` — ``textOf``, ``setText``: its text; ``fail``: what went
 * wrong, said to the reader (the file is no program; it runs but was not saved).
 */
export function useFirmwareFile(live: Live, textOf: (id: string) => string, setText: (id: string, text: string) => void,
                                fail: (message: string) => void) {
  const { t } = useTranslation("simulation");
  const upload = useAtomSet(uploadFirmware, { mode: "promiseExit" });
  return useCallback(async (id: string, file: File) => {
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (!bytes.length || bytes.length > FIRMWARE_MAX) return fail(t("firmware.size", { name: file.name, size: bytes.length }));
    let image: Uint8Array;
    try {
      image = flashOf(bytes);
    } catch (e) {
      return fail(t("firmware.invalid", { name: file.name, error: e instanceof Error ? e.message : String(e) }));
    }
    const exit = await upload({ payload: bytes });
    if (exit._tag === "Success") {
      const text = withFirmware(textOf(id), firmwareUrl(exit.value.id, file.name));
      setText(id, text);
      live.runFile(id, image, text);
      return;
    }
    live.runFile(id, image, textOf(id));
    const tag = failure(exit.cause)?._tag;
    fail(t("firmware.notSaved", {
      name: file.name,
      why: t(tag === "Unauthorized" ? "firmware.signedOut" : tag === "FirmwareQuota" ? "firmware.quota" : "firmware.unreachable"),
    }));
  }, [live, textOf, setText, fail, upload, t]);
}

