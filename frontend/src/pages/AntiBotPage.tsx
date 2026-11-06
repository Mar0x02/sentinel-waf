import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AntiBotSettings, api, Site } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useLanguage } from "../i18n/LanguageContext";

const emptySettings: AntiBotSettings = {
  bot_challenge_enabled: false,
  honeypot_checkbox_enabled: false,
  honeypot_path_enabled: false,
  block_bad_user_agents: false,
};

export function AntiBotPage() {
  const { t } = useLanguage();
  const { canWrite } = useAuth();
  const [sites, setSites] = useState<Site[]>([]);
  const [siteId, setSiteId] = useState<number | null>(null);
  const [settings, setSettings] = useState<AntiBotSettings>(emptySettings);

  useEffect(() => {
    api.listSites().then((list) => {
      setSites(list);
      if (list.length > 0) setSiteId(list[0].id);
    });
  }, []);

  useEffect(() => {
    const site = sites.find((s) => s.id === siteId);
    if (site) {
      setSettings({
        bot_challenge_enabled: site.bot_challenge_enabled,
        honeypot_checkbox_enabled: site.honeypot_checkbox_enabled,
        honeypot_path_enabled: site.honeypot_path_enabled,
        block_bad_user_agents: site.block_bad_user_agents,
      });
    }
  }, [siteId, sites]);

  async function save() {
    if (siteId === null) return;
    try {
      const updated = await api.updateAntiBot(siteId, settings);
      setSites(sites.map((s) => (s.id === siteId ? updated : s)));
      toast.success(t("antiBot.saveSuccess"));
    } catch (e) {
      toast.error(String(e));
    }
  }

  return (
    <div>
      <h2>{t("antiBot.title")}</h2>
      <p className="muted">{t("antiBot.description")}</p>

      <div className="card">
        <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
          {t("antiBot.selectSite")}
          <select value={siteId ?? ""} onChange={(e) => setSiteId(Number(e.target.value))}>
            {sites.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.domain})
              </option>
            ))}
          </select>
        </label>

        {sites.length === 0 ? (
          <p className="muted">{t("antiBot.noSites")}</p>
        ) : (
          <>
            <label className="toggle-option toggle-option-first">
              <input
                type="checkbox"
                checked={settings.bot_challenge_enabled}
                disabled={!canWrite}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    bot_challenge_enabled: e.target.checked,
                    honeypot_checkbox_enabled: e.target.checked ? settings.honeypot_checkbox_enabled : false,
                  })
                }
              />
              {t("antiBot.jsChallenge")}
            </label>
            <p className="muted">{t("antiBot.jsChallengeDescription")}</p>

            <label className="toggle-option">
              <input
                type="checkbox"
                checked={settings.honeypot_checkbox_enabled}
                disabled={!canWrite || !settings.bot_challenge_enabled}
                onChange={(e) => setSettings({ ...settings, honeypot_checkbox_enabled: e.target.checked })}
              />
              {t("antiBot.honeypotCheckbox")}
            </label>
            <p className="muted">
              {settings.bot_challenge_enabled
                ? t("antiBot.honeypotCheckboxDescription")
                : t("antiBot.honeypotCheckboxRequiresJs")}
            </p>

            <label className="toggle-option">
              <input
                type="checkbox"
                checked={settings.honeypot_path_enabled}
                disabled={!canWrite}
                onChange={(e) => setSettings({ ...settings, honeypot_path_enabled: e.target.checked })}
              />
              {t("antiBot.honeypotPath")}
            </label>
            <p className="muted">{t("antiBot.honeypotPathDescription")}</p>

            <label className="toggle-option">
              <input
                type="checkbox"
                checked={settings.block_bad_user_agents}
                disabled={!canWrite}
                onChange={(e) => setSettings({ ...settings, block_bad_user_agents: e.target.checked })}
              />
              {t("antiBot.blockBadUa")}
            </label>
            <p className="muted">{t("antiBot.blockBadUaDescription")}</p>

            {canWrite && (
              <div style={{ marginTop: 14 }}>
                <button className="btn btn-primary" onClick={save}>
                  {t("common.save")}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
