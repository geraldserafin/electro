/** Programs for a board given whole — a Pico's UF2, or its flash image — uploaded by a signed-in user and
 *  kept by what is in them: the SHA-256 of their bytes is their id (the same file twice is kept once, and
 *  never changes). A note names one on its board's first line (``// firmware: /api/firmware/<id>/doom.uf2``,
 *  the name only for the reader); whoever has the note can run it, so fetching one needs no session —
 *  its id, which no one guesses, is enough. */
import { HttpApiEndpoint, HttpApiGroup, HttpApiSchema } from "@effect/platform";
import { Schema } from "effect";
import { Authentication } from "./Auth.js";

export const FirmwareId = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/));
export type FirmwareId = typeof FirmwareId.Type;

/** A file at most: a Pico's flash (16 MB); a user's files together at most. */
export const FIRMWARE_MAX = 16 * 1024 * 1024;
export const FIRMWARE_QUOTA = 256 * 1024 * 1024;

export const Uploaded = Schema.Struct({ id: FirmwareId, size: Schema.Int });

/** Empty, or larger than FIRMWARE_MAX. */
export class FirmwareSize extends Schema.TaggedError<FirmwareSize>()(
  "FirmwareSize",
  { size: Schema.Int, max: Schema.Int },
  HttpApiSchema.annotations({ status: 413 }),
) {
  get message() {
    return `A firmware file of ${this.size} bytes: it must be 1 to ${this.max}.`;
  }
}

/** The user's files would take more than FIRMWARE_QUOTA together. */
export class FirmwareQuota extends Schema.TaggedError<FirmwareQuota>()(
  "FirmwareQuota",
  { used: Schema.Int, quota: Schema.Int },
  HttpApiSchema.annotations({ status: 413 }),
) {
  get message() {
    return `Firmware files take ${this.used} bytes of the ${this.quota} a user may keep.`;
  }
}

export class FirmwareNotFound extends Schema.TaggedError<FirmwareNotFound>()(
  "FirmwareNotFound",
  { id: Schema.String },
  HttpApiSchema.annotations({ status: 404 }),
) {
  get message() {
    return `No firmware file ${this.id}.`;
  }
}

/** Uploading: signed-in users only. */
export class FirmwareGroup extends HttpApiGroup.make("firmware")
  .add(
    HttpApiEndpoint.post("upload", "/firmware")
      .setPayload(HttpApiSchema.Uint8Array())
      .addSuccess(Uploaded)
      .addError(FirmwareSize)
      .addError(FirmwareQuota),
  )
  .middleware(Authentication) {}

/** Fetching one by its id (and any name after it): no session needed. */
export class FirmwareFilesGroup extends HttpApiGroup.make("firmwareFiles").add(
  HttpApiEndpoint.get("get", "/firmware/:id/:name")
    .setPath(Schema.Struct({ id: Schema.String, name: Schema.String }))
    .addSuccess(HttpApiSchema.Uint8Array())
    .addError(FirmwareNotFound),
) {}
