"use client";

import { useAuth } from "@carebridge/api-client/react";
import { errorMessage, useT } from "@carebridge/i18n";
import { Alert, Button, Card, Field, Logo, TextInput } from "@carebridge/ui";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { DEMO_ACCOUNT, SHOW_DEMO_ACCOUNT } from "@/lib/demo";

export default function DoctorLoginPage() {
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
    <div className="flex min-h-screen items-center justify-center bg-brand-strong px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-3 text-white">
          <Logo size={36} />
          <p className="text-xl font-semibold">
            {t("app.name")} <span className="font-normal text-white/70">· {t("nav.clinician")}</span>
          </p>
        </div>
        <Card>
          <h1 className="text-xl font-semibold">{t("login.title")}</h1>
          <p className="mt-1 text-muted">{t("login.subtitle")}</p>
          <form onSubmit={submit} className="mt-5 flex flex-col gap-4">
            <Field label={t("login.email")}>
              {(p) => (
                <TextInput {...p} type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
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
          {SHOW_DEMO_ACCOUNT ? (
            <div className="mt-5 border-t border-line pt-4 text-sm">
              <p className="font-semibold text-muted">{t("login.demoTitle")}</p>
              <p className="mt-1 font-mono">
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
        </Card>
      </div>
    </div>
  );
}
