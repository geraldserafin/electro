// Compiling an Arduino sketch on the server (@electro/notes-api: ArduinoGroup); a firmware file kept there (FirmwareGroup).
import { NotesClient } from "@/features/notes/atoms";

export const compileSketch = NotesClient.mutation("arduino", "compile");
export const uploadFirmware = NotesClient.mutation("firmware", "upload");
