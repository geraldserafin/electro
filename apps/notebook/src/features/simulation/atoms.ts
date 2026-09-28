// Compiling an Arduino sketch on the server (@electro/notes-api: ArduinoGroup).
import { NotesClient } from "@/features/notes/atoms";

export const compileSketch = NotesClient.mutation("arduino", "compile");
