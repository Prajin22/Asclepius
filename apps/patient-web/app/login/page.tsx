"use client";

import { useAuth } from "@carebridge/api-client/react";
import { errorMessage, useT } from "@carebridge/i18n";
import { Alert, Button, Card, Field, Logo, TextInput } from "@carebridge/ui";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { DEMO_ACCOUNT, SHOW_DEMO_ACCOUNT } from "@/lib/demo";

export default function LoginPage() {
  const { login, session, ready } = useAuth();
  const router = useRouter();
  const t = useT();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (ready && session) router.replace("/");
  }, [ready, session, router]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      router.replace("/");
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <div className="flex justify-end px-4 py-4 sm:px-6">
        <LanguageSwitcher />
      </div>
      <main className="flex flex-1 items-start justify-center px-4 pb-16 pt-4 sm:items-center">
        <div className="w-full max-w-md">
          <div className="mb-6 flex flex-col items-center text-center">
            <Logo size={44} />
            <p className="mt-3 text-2xl font-semibold text-brand-strong">{t("app.name")}</p>
            <p className="mt-1 text-muted">{t("app.tagline")}</p>
          </div>
          <Card>
            <h1 className="text-xl font-semibold">{t("login.title")}</h1>
            <p className="mt-1 text-muted">{t("login.subtitle")}</p>
            <form onSubmit={submit} className="mt-5 flex flex-col gap-4">
              <Field label={t("login.email")}>
                {(p) => (
                  <TextInput
                    {...p}
                    type="email"
                    autoComplete="username"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                )}
              </Field>
              <Field label={t("login.password")}>
                {(p) => (
                  <TextInput
                    {...p}
                    type="password"
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                )}
              </Field>
              {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
              <Button type="submit" size="lg" disabled={busy}>
                {busy ? t("login.submitting") : t("login.submit")}
              </Button>
            </form>
          </Card>
          {SHOW_DEMO_ACCOUNT ? (
            <div className="mt-4 rounded-xl border border-dashed border-line-strong bg-surface px-4 py-3 text-sm">
              <p className="font-semibold text-muted">{t("login.demoTitle")}</p>
              <p className="mt-1 font-mono text-ink">
                {DEMO_ACCOUNT.email} / {DEMO_ACCOUNT.password}
              </p>
              <Button
                variant="ghost"
                size="sm"
                className="mt-1 -ml-3"
                onClick={() => {
                  setEmail(DEMO_ACCOUNT.email);
                  setPassword(DEMO_ACCOUNT.password);
                }}
              >
                {t("login.demoFill")}
              </Button>
            </div>
          ) : null}
        </div>
      </main>
    </div>
  );
}
