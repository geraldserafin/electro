// The account's group in the settings menu: who is signed in, and signing out (then the page
// afresh: nothing of theirs stays in memory).
import { Result, useAtomSet, useAtomValue } from "@effect-atom/atom-react";
import { useTranslation } from "react-i18next";
import { Avatar } from "@/shared/ui/Avatar";
import { SignOut } from "@/shared/ui/icons";
import { MenuGroup, MenuItem } from "@/shared/ui/Menu";
import { logout, meAtom } from "./atoms";

export function Account() {
  const { t } = useTranslation("auth");
  const me = useAtomValue(meAtom);
  const signOut = useAtomSet(logout, { mode: "promiseExit" });
  if (!Result.isSuccess(me)) return null;
  const user = me.value;
  return (
    <MenuGroup label={t("account")}>
      <div className="flex items-center gap-2.5 px-4 py-1.5">
        <Avatar name={user.name} url={user.avatarUrl} />
        <span className="grid min-w-0">
          <span className="truncate text-[14px]">{user.name}</span>
          {user.email && <span className="truncate text-[12px] text-muted">{user.email}</span>}
        </span>
      </div>
      <MenuItem icon={<SignOut />} onSelect={async () => { await signOut({}); location.assign("/"); }}>{t("signOut")}</MenuItem>
    </MenuGroup>
  );
}
