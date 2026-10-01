"use client";

import { useAuth, useQuery } from "@carebridge/api-client/react";
import { errorMessage, useT } from "@carebridge/i18n";
import { Alert, Button, Card, Field, TextInput } from "@carebridge/ui";
import { ArrowLeft } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { SAKTI_DEMO_ACCOUNTS, SHOW_DEMO_ACCOUNT } from "@/lib/demo";
import { acceptsRole } from "@/lib/product";
import { HOME_FOR_ROLE } from "@/lib/routes";

/**
 * Signing in to IP-SAKTI Sahayak. There is no role to pick: where someone lands
 * comes from their account. There is no sign-up yet — accounts are issued.
 */
export function SaktiSignIn() {
  const t = useT();
  return (
    <div className="flex min-h-[100dvh] flex-col">
      <header className="flex items-center justify-between gap-3 px-5 py-4 sm:px-8">
        <Link href="/" className="inline-flex items-center gap-1.5 text-small font-medium text-brand-strong hover:underline">
          <ArrowLeft size={16} aria-hidden />
          {t("app.name")}
        </Link>
        <LanguageSwitcher />
      </header>
      <main className="flex flex-1 justify-center px-5 pb-16 sm:px-8 lg:items-center">
        <SignInPanel />
      </main>
      <footer className="px-5 pb-6 sm:px-8">
        <p className="mx-auto max-w-md text-center text-caption text-subtle">{t("disclaimer.prototype")}</p>
      </footer>
    </div>
  );
}

function SignInPanel() {
  const t = useT();
  const router = useRouter();
  const { session, ready, login, logout } = useAuth();
  // Built for IP-SAKTI but pointed at an API running the other product, every
  // sign-in would fail as "wrong password". Say what is actually wrong.
  const product = useQuery((api) => api.meta.product());
  const wrongProduct = product.data !== undefined && product.data.product !== "ip_sakti";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const leaving = useRef(false);

  useEffect(() => {
    if (ready && session && !leaving.current && acceptsRole(session.user.role, "ip_sakti")) {
      router.replace(HOME_FOR_ROLE[session.user.role]);
    }
  }, [ready, session, router]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const s = await login(email.trim(), password);
      if (!acceptsRole(s.user.role, "ip_sakti")) {
        // The API refuses other products' accounts; this is belt and braces.
        logout();
        setError({ code: "wrong_role" });
        return;
      }
      leaving.current = true;
      router.replace(HOME_FOR_ROLE[s.user.role]);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="w-full max-w-md" padding="lg" aria-labelledby="sign-in-title">
      <h1 id="sign-in-title" className="text-page text-ink">
        {t("signIn.title")}
      </h1>
      <p className="mt-1.5 text-muted">{t("signIn.description")}</p>

      {wrongProduct ? (
        <Alert tone="error" className="mt-5">
          {t("signIn.wrongProduct")}
        </Alert>
      ) : null}

      <form onSubmit={submit} className="mt-6 flex flex-col gap-4" noValidate>
        <Field label={t("signIn.email")}>
          {(p) => (
            <TextInput
              {...p}
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          )}
        </Field>
        <Field label={t("signIn.password")}>
          {(p) => (
            <TextInput
              {...p}
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          )}
        </Field>
        {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
        <Button type="submit" disabled={busy || !email || !password}>
          {busy ? t("actions.signingIn") : t("actions.signIn")}
        </Button>
      </form>

      {SHOW_DEMO_ACCOUNT ? (
        <section aria-labelledby="demo-accounts" className="mt-6 border-t border-line pt-5">
          <h2 id="demo-accounts" className="text-label uppercase text-subtle">
            {t("signIn.demoTitle")}
          </h2>
          <ul className="mt-3 grid grid-cols-2 gap-2">
            {SAKTI_DEMO_ACCOUNTS.map((account) => (
              <li key={account.email}>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  className="w-full"
                  onClick={() => {
                    setEmail(account.email);
                    setPassword(account.password);
                    setError(null);
                  }}
                >
                  {t("signIn.demoFill", { role: t(`role.${account.role}`) })}
                </Button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </Card>
  );
}
