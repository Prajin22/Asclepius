"use client";

import { useAuth } from "@carebridge/api-client/react";
import { errorMessage, useT } from "@carebridge/i18n";
import { Alert, Button, Card, Field, Logo, ProvenanceLegend, TextInput, buttonClasses } from "@carebridge/ui";
import { ArrowLeft } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
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
    if (ready && session) router.replace("/home");
  }, [ready, session, router]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      router.replace("/home");
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-[100dvh] flex-col">
      <header className="flex items-center justify-between gap-3 px-5 py-4 sm:px-8">
        <Link href="/" className="inline-flex items-center gap-1.5 text-small font-medium text-brand hover:underline">
          <ArrowLeft size={16} aria-hidden />
          {t("app.name")}
        </Link>
        <LanguageSwitcher />
      </header>

      <main className="flex flex-1 items-center justify-center px-5 pb-16 sm:px-8">
        <div className="grid w-full max-w-4xl items-center gap-10 lg:grid-cols-2 lg:gap-16">
          {/* Why this product exists, next to the door into it. */}
          <div className="hidden lg:block">
            <Logo size={40} className="text-brand" />
            <h1 className="mt-5 text-title text-balance text-ink">{t("landing.hero.title")}</h1>
            <p className="mt-3 max-w-md text-body-lg text-muted">{t("landing.hero.subtitle")}</p>
            <ProvenanceLegend className="mt-7" />
          </div>

          <div className="w-full max-w-md justify-self-center lg:justify-self-end">
            <div className="mb-5 flex flex-col items-center text-center lg:hidden">
              <Logo size={38} className="text-brand" />
              <p className="mt-2.5 text-heading tracking-tight text-brand-strong">{t("app.name")}</p>
              <p className="mt-1 text-small text-muted">{t("app.tagline")}</p>
            </div>

            <Card padding="lg">
              <h2 className="text-heading tracking-tight text-ink">{t("login.title")}</h2>
              <p className="mt-1 text-muted">{t("login.subtitle")}</p>
              <form onSubmit={submit} className="mt-6 flex flex-col gap-4">
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
                <Button type="submit" size="lg" loading={busy}>
                  {busy ? t("login.submitting") : t("login.submit")}
                </Button>
              </form>
            </Card>

            {SHOW_DEMO_ACCOUNT ? (
              <div className="mt-4 rounded-xl border border-dashed border-line-strong bg-surface px-4 py-3.5">
                <p className="text-label uppercase text-subtle">{t("login.demoTitle")}</p>
                <p className="mt-1.5 font-mono text-small text-ink">
                  {DEMO_ACCOUNT.email} / {DEMO_ACCOUNT.password}
                </p>
                <button
                  type="button"
                  className={buttonClasses("ghost", "sm", "mt-1 -ml-3")}
                  onClick={() => {
                    setEmail(DEMO_ACCOUNT.email);
                    setPassword(DEMO_ACCOUNT.password);
                  }}
                >
                  {t("login.demoFill")}
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </main>
    </div>
  );
}
