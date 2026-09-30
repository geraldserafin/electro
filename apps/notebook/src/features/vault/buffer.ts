// isomorphic-git takes Node's Buffer as given: in the page, the buffer package's.
import { Buffer } from "buffer";

globalThis.Buffer ??= Buffer;
