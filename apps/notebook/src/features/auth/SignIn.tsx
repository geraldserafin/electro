// The sign-in page: a button per provider the server has. Each is a link to the server, which
// sends the browser to the provider and, signed in, back here (the address it was at).
import { Result, useAtomValue } from "@effect-atom/atom-react";
import type { Provider } from "@electro/notes-api";
import { useTranslation } from "react-i18next";
import { SettingsMenu } from "@/features/settings";
import { Brand, Islands } from "@/shared/ui/Island";
import { GitHubLogo, GoogleLogo, MicrosoftLogo } from "@/shared/ui/icons";
import { providersAtom } from "./atoms";

const LOGO: Record<Provider, () => React.JSX.Element> = {
  google: GoogleLogo,
  github: GitHubLogo,
  microsoft: MicrosoftLogo,
};

export function SignIn() {
  const { t } = useTranslation("auth");
  const providers = useAtomValue(providersAtom);
  const here = new URL(location.href);
  const failed = here.searchParams.get("signin") === "failed";
  here.searchParams.delete("signin");
  const returnTo = encodeURIComponent(here.pathname + here.search);

  return (
    <div>
      <Islands side="left">
        <Brand />
      </Islands>
      <Islands side="right">
        <SettingsMenu />
      </Islands>
      <main className="grid min-h-dvh place-items-center px-6">
        <div className="grid w-full max-w-90 gap-3">
          <h1 className="m-0 text-[22px] font-medium">{t("title")}</h1>
          <p className="m-0 mb-3 text-[15px] text-muted">{t("lead")}</p>
          {failed && (
            <p role="alert" className="m-0 text-[14px] text-danger">
              {t("failed")}
            </p>
          )}
          {Result.builder(providers)
            .onInitial(() => null)
            .onSuccess((list) =>
              list.length === 0 ? (
                <p className="m-0 text-[14px] text-muted">{t("none")}</p>
              ) : (
                list.map((p) => {
                  const Logo = LOGO[p];
                  return (
                    <a
                      key={p}
                      href={`/api/auth/${p}?returnTo=${returnTo}`}
                      className="flex items-center justify-center gap-3 h-11.5 rounded-xl border border-line bg-surface text-[15px] text-fg no-underline hover:bg-selected"
                    >
                      <Logo />
                      {t(`with.${p}`)}
                    </a>
                  );
                })
              ),
            )
            .onFailure(() => <p className="m-0 text-[14px] text-muted">{t("unreachable")}</p>)
            .render()}
        </div>
      </main>
    </div>
  );
}
