/**
 * The notes server: the API under /api (docs at /api/docs), SQLite underneath.
 *
 *   PORT=5191 DATABASE_PATH=.data/notes.sqlite pnpm dev
 */
import { HttpApiBuilder, HttpApiSwagger, HttpMiddleware, HttpServer } from "@effect/platform"
import { NodeHttpServer, NodeRuntime } from "@effect/platform-node"
import { Config, Effect, Layer } from "effect"
import { createServer } from "node:http"
import * as Database from "./Database.js"
import { ApiLive } from "./Http.js"

const HttpLive = Layer.unwrapEffect(
  Effect.gen(function* () {
    const port = yield* Config.integer("PORT").pipe(Config.withDefault(5191))
    return HttpApiBuilder.serve(HttpMiddleware.logger).pipe(
      Layer.provide(HttpApiSwagger.layer({ path: "/api/docs" })),
      Layer.provide(ApiLive),
      HttpServer.withLogAddress,
      Layer.provide(NodeHttpServer.layer(createServer, { port })),
    )
  }),
).pipe(Layer.provide(Database.layerConfig))

NodeRuntime.runMain(Layer.launch(HttpLive))
