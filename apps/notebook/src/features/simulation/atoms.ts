// A firmware file kept on the notes server (@electro/notes-api: FirmwareGroup).
import { NotesClient } from "@/features/notes/atoms";

export const uploadFirmware = NotesClient.mutation("firmware", "upload");
