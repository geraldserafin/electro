/**
 * The OAuth providers this server signs in with (arctic does the OAuth 2.0 part). Each one is on
 * when its app's id and secret are configured (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET, and
 * the same for GITHUB_ and MICROSOFT_); the provider sends the browser back to
 * PUBLIC_URL/api/auth/<provider>/callback, which has to be registered with the app.
 */
import type { Provider } from "@electro/notes-api";
import * as arctic from "arctic";
import { Config, Context, Data, Effect, Layer, Option, Redacted } from "effect";
import type { Profile } from "./Accounts.js";

export class ProviderError extends Data.TaggedError("ProviderError")<{ readonly cause: unknown }> {}

export interface OAuthProvider {
  /** The consent screen's address; the verifier is PKCE's (only the providers that use it). */
  readonly authorizationUrl: (state: string, codeVerifier: string) => URL;
  /** Who signed in, from the code the provider sent back. */
  readonly profile: (code: string, codeVerifier: string) => Effect.Effect<Profile, ProviderError>;
}

export class Providers extends Context.Tag("Providers")<Providers, Partial<Record<Provider, OAuthProvider>>>() {}

const call = <A>(f: () => Promise<A>) => Effect.tryPromise({ try: f, catch: (cause) => new ProviderError({ cause }) });

const google = (id: string, secret: string, redirect: string): OAuthProvider => {
  const client = new arctic.Google(id, secret, redirect);
  return {
    authorizationUrl: (state, verifier) =>
      client.createAuthorizationURL(state, verifier, ["openid", "profile", "email"]),
    profile: (code, verifier) =>
      call(async () => {
        const tokens = await client.validateAuthorizationCode(code, verifier);
        // straight from Google's token endpoint (over TLS): no need to check the signature
        const claims = arctic.decodeIdToken(tokens.idToken()) as {
          sub: string;
          name?: string;
          email?: string;
          email_verified?: boolean;
          picture?: string;
        };
        const email = claims.email_verified ? (claims.email ?? null) : null;
        return {
          provider: "google",
          id: claims.sub,
          name: claims.name ?? claims.email ?? "Google",
          email,
          avatarUrl: claims.picture ?? null,
        };
      }),
  };
};

const github = (id: string, secret: string, redirect: string): OAuthProvider => {
  const client = new arctic.GitHub(id, secret, redirect);
  const get = async <A>(token: string, path: string): Promise<A> => {
    const response = await fetch(`https://api.github.com${path}`, {
      headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json", "User-Agent": "electro" },
    });
    if (!response.ok) throw new Error(`GitHub ${path}: ${response.status}`);
    return response.json() as Promise<A>;
  };
  return {
    authorizationUrl: (state) => client.createAuthorizationURL(state, ["user:email"]),
    profile: (code) =>
      call(async () => {
        const token = (await client.validateAuthorizationCode(code)).accessToken();
        const [user, emails] = await Promise.all([
          get<{ id: number; login: string; name: string | null; avatar_url: string | null }>(token, "/user"),
          get<Array<{ email: string; primary: boolean; verified: boolean }>>(token, "/user/emails"),
        ]);
        const email = emails.find((e) => e.primary && e.verified)?.email ?? null;
        return {
          provider: "github",
          id: String(user.id),
          name: user.name ?? user.login,
          email,
          avatarUrl: user.avatar_url,
        };
      }),
  };
};

const microsoft = (id: string, secret: string, redirect: string): OAuthProvider => {
  const client = new arctic.MicrosoftEntraId("common", id, secret, redirect); // work, school and personal accounts
  return {
    authorizationUrl: (state, verifier) =>
      client.createAuthorizationURL(state, verifier, ["openid", "profile", "email"]),
    profile: (code, verifier) =>
      call(async () => {
        const tokens = await client.validateAuthorizationCode(code, verifier);
        const claims = arctic.decodeIdToken(tokens.idToken()) as {
          sub: string;
          name?: string;
          preferred_username?: string;
        };
        // Microsoft does not vouch for the email (any tenant can claim any address): never matched to a user
        return {
          provider: "microsoft",
          id: claims.sub,
          name: claims.name ?? claims.preferred_username ?? "Microsoft",
          email: null,
          avatarUrl: null,
        };
      }),
  };
};

const makers = { google, github, microsoft } satisfies Record<Provider, unknown>;

/** The providers from the environment; the ones without an id and a secret are off. */
export const layerConfig = Layer.effect(
  Providers,
  Effect.gen(function* () {
    const publicUrl = yield* Config.string("PUBLIC_URL").pipe(Config.withDefault("http://localhost:5190"));
    const providers: Partial<Record<Provider, OAuthProvider>> = {};
    for (const [name, make] of Object.entries(makers) as Array<[Provider, typeof google]>) {
      const prefix = name.toUpperCase();
      const app = yield* Config.option(
        Config.all([Config.string(`${prefix}_CLIENT_ID`), Config.redacted(`${prefix}_CLIENT_SECRET`)]),
      );
      if (Option.isNone(app)) continue;
      const [id, secret] = app.value;
      providers[name] = make(id, Redacted.value(secret), `${publicUrl}/api/auth/${name}/callback`);
    }
    yield* Effect.logInfo(
      `Logowanie przez: ${Object.keys(providers).join(", ") || "(nic — brak *_CLIENT_ID i *_CLIENT_SECRET)"}`,
    );
    return providers;
  }),
);
