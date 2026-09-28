// The app, for someone signed in; for no one, the sign-in page. A server that does not answer is
// not "no one": the app shows, and says so where it needs the server.
import { Result, useAtomValue } from "@effect-atom/atom-react";
import type { ReactNode } from "react";
import { meAtom } from "./atoms";
import { SignIn } from "./SignIn";

export function AuthGate({ children }: { children: ReactNode }) {
  return Result.builder(useAtomValue(meAtom))
    .onInitial(() => null)
    .onErrorTag("Unauthorized", () => <SignIn />)
    .orElse(() => children);
}
