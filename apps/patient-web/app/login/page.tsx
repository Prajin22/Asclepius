"use client";

import { useAuth } from "@carebridge/api-client/react";
import { errorMessage, useI18n, useT } from "@carebridge/i18n";
import { LANGUAGES, UI_LANGUAGES, isLanguageCode, type LanguageCode, type Role } from "@carebridge/shared-types";
import {
  Alert,
  Button,
  Card,
  Field,
  Logo,
  ProvenanceLegend,
  SegmentedTabs,
  Select,
  TextInput,
  buttonClasses,
  cn,
} from "@carebridge/ui";
import { ArrowLeft, ShieldCheck, Stethoscope, User } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  DoctorDetailsFields,
  EMPTY_DOCTOR_DETAILS,
  detailsFromDraft,
  isDraftComplete,
  type DoctorDetailsDraft,
} from "@/components/DoctorDetailsFields";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { DEMO_ACCOUNTS, SHOW_DEMO_ACCOUNT, type DemoAccountKey } from "@/lib/demo";
import { DOCTOR_APPLICATION_PATH, HOME_FOR_ROLE } from "@/lib/routes";

/** Administrators sign in here too, but nobody chooses to sign up as one. */
type ChosenRole = Extract<Role, "patient" | "doctor">;
type Mode = "signIn" | "create";

const DEMOS: Record<ChosenRole, DemoAccountKey[]> = {
  patient: ["patient"],
  doctor: ["doctor", "pendingDoctor"],
};

/**
 * The one door into Asclepius. Everyone picks who they are, then signs in or
 * creates an account; where they land afterwards comes from the account itself.
 */
export default function AuthPage() {
  const t = useT();
  return (
    <div className="flex min-h-[100dvh] flex-col">
      <header className="flex items-center justify-between gap-3 px-5 py-4 sm:px-8">
        <Link href="/" className="inline-flex items-center gap-1.5 text-small font-medium text-brand hover:underline">
          <ArrowLeft size={16} aria-hidden />
          {t("app.name")}
        </Link>
        <LanguageSwitcher />
      </header>
      <main className="flex flex-1 justify-center px-5 pb-16 sm:px-8 lg:items-center">
        {/* The role and mode can be preset from a link (?role=doctor&mode=create). */}
        <Suspense fallback={null}>
          <AuthPanel />
        </Suspense>
      </main>
    </div>
  );
}

function AuthPanel() {
  const params = useSearchParams();
  const { session, ready, login, register, applyAsDoctor } = useAuth();
  const router = useRouter();
  const { t, locale } = useI18n();

  const [role, setRole] = useState<ChosenRole>(params.get("role") === "doctor" ? "doctor" : "patient");
  const [mode, setMode] = useState<Mode>(params.get("mode") === "create" ? "create" : "signIn");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [language, setLanguage] = useState<LanguageCode | null>(null);
  const [details, setDetails] = useState<DoctorDetailsDraft>(EMPTY_DOCTOR_DETAILS);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  // Set while this page sends someone onward, so the "already signed in" redirect stays out of the way.
  const leaving = useRef(false);

  useEffect(() => {
    if (ready && session && !leaving.current) router.replace(HOME_FOR_ROLE[session.user.role]);
  }, [ready, session, router]);

  const applying = mode === "create" && role === "doctor";
  const preferredLanguage = language ?? (isLanguageCode(locale) ? locale : UI_LANGUAGES[0]);

  const chooseRole = (next: ChosenRole) => {
    setRole(next);
    setError(null);
  };

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    leaving.current = true;
    try {
      if (mode === "signIn") {
        const s = await login(email, password);
        router.replace(HOME_FOR_ROLE[s.user.role]);
      } else if (role === "patient") {
        await register({ email, password, display_name: name.trim(), preferred_language: preferredLanguage });
        router.replace(HOME_FOR_ROLE.patient);
      } else {
        await applyAsDoctor({ ...detailsFromDraft(details), email, password });
        router.replace(DOCTOR_APPLICATION_PATH);
      }
    } catch (err) {
      leaving.current = false;
      setError(err);
      setBusy(false);
    }
  }

  const submitLabel =
    mode === "signIn"
      ? busy ? t("auth.signingIn") : t("auth.signIn")
      : role === "patient"
        ? busy ? t("auth.registering") : t("auth.register")
        : busy ? t("auth.applying") : t("auth.apply");

  return (
    <div
      className={cn(
        "grid w-full items-center gap-10 py-2 lg:gap-16",
        applying ? "max-w-2xl" : "max-w-4xl lg:grid-cols-2",
      )}
    >
      {/* Why this product exists, beside the door into it. The long doctor form gets the full width. */}
      {applying ? null : (
        <div className="hidden lg:block">
          <Logo size={40} className="text-brand" />
          <p className="mt-5 text-title text-balance text-ink">
            {role === "doctor" ? t("auth.doctorPitch.title") : t("landing.hero.title")}
          </p>
          <p className="mt-3 max-w-md text-body-lg text-muted">
            {role === "doctor" ? t("auth.doctorPitch.body") : t("landing.hero.subtitle")}
          </p>
          <ProvenanceLegend className="mt-7" />
        </div>
      )}

      <div className={cn("w-full justify-self-center", applying ? "" : "max-w-md lg:justify-self-end")}>
        <Card padding="lg">
          <div className="flex items-center gap-2.5 lg:hidden">
            <Logo size={28} className="text-brand" />
          </div>
          <h1 className="mt-3 text-heading tracking-tight text-ink lg:mt-0">{t("auth.title")}</h1>

          <fieldset className="mt-5">
            <legend className="text-small font-semibold text-muted">{t("auth.roleLabel")}</legend>
            <div className="mt-2 grid grid-cols-2 gap-2.5">
              <RoleOption
                value="patient"
                selected={role}
                onSelect={chooseRole}
                icon={<User size={20} weight="bold" aria-hidden />}
                title={t("auth.role.patient")}
                hint={t("auth.role.patientHint")}
              />
              <RoleOption
                value="doctor"
                selected={role}
                onSelect={chooseRole}
                icon={<Stethoscope size={20} weight="bold" aria-hidden />}
                title={t("auth.role.doctor")}
                hint={t("auth.role.doctorHint")}
              />
            </div>
            {/* On a phone the cards only have room for a title; the chosen role's hint sits below. */}
            <p className="mt-2 text-small text-muted sm:hidden">
              {role === "doctor" ? t("auth.role.doctorHint") : t("auth.role.patientHint")}
            </p>
          </fieldset>

          <SegmentedTabs
            size="sm"
            className="mt-5"
            label={t("auth.modeLabel")}
            value={mode}
            onChange={(next) => {
              setMode(next);
              setError(null);
            }}
            items={[
              { value: "signIn", label: t("auth.mode.signIn") },
              { value: "create", label: role === "doctor" ? t("auth.mode.apply") : t("auth.mode.register") },
            ]}
          />

          <form onSubmit={submit} className="mt-5 flex flex-col gap-4">
            {applying ? (
              <>
                <p className="flex gap-2.5 rounded-lg bg-brand-tint px-3.5 py-3 text-small text-brand-strong">
                  <ShieldCheck size={18} className="mt-0.5 shrink-0" aria-hidden />
                  {t("auth.applyIntro")}
                </p>
                <DoctorDetailsFields value={details} onChange={setDetails} />
              </>
            ) : null}

            {mode === "create" && role === "patient" ? (
              <Field label={t("auth.name")}>
                {(p) => (
                  <TextInput
                    {...p}
                    autoComplete="name"
                    required
                    maxLength={200}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                )}
              </Field>
            ) : null}

            <div className={cn("flex flex-col gap-4", applying && "sm:grid sm:grid-cols-2")}>
              <Field label={t("auth.email")}>
                {(p) => (
                  <TextInput
                    {...p}
                    type="email"
                    autoComplete={mode === "create" ? "email" : "username"}
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                )}
              </Field>
              <Field label={t("auth.password")} hint={mode === "create" ? t("auth.passwordHint") : undefined}>
                {(p) => (
                  <TextInput
                    {...p}
                    type="password"
                    autoComplete={mode === "create" ? "new-password" : "current-password"}
                    required
                    minLength={mode === "create" ? 8 : undefined}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                )}
              </Field>
            </div>

            {mode === "create" && role === "patient" ? (
              <Field label={t("auth.language")} hint={t("auth.languageHint")}>
                {(p) => (
                  <Select
                    {...p}
                    value={preferredLanguage}
                    onChange={(e) => {
                      if (isLanguageCode(e.target.value)) setLanguage(e.target.value);
                    }}
                  >
                    {LANGUAGES.map((l) => (
                      <option key={l.code} value={l.code}>
                        {l.nativeName === l.englishName ? l.englishName : `${l.nativeName} · ${l.englishName}`}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            ) : null}

            {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
            <Button type="submit" size="lg" loading={busy} disabled={applying && !isDraftComplete(details)}>
              {submitLabel}
            </Button>
          </form>
        </Card>

        {SHOW_DEMO_ACCOUNT && mode === "signIn" ? (
          <div className="mt-4 rounded-xl border border-dashed border-line-strong bg-surface px-4 py-3.5">
            <p className="text-small font-semibold text-muted">{t("auth.demoTitle")}</p>
            <ul className="mt-2 flex flex-col gap-2.5">
              {DEMOS[role].map((key) => {
                const account = DEMO_ACCOUNTS[key];
                const label = t(`auth.demo.${key}`);
                return (
                  <li key={key} className="flex items-center justify-between gap-3">
                    <span className="min-w-0">
                      <span className="block text-small font-medium text-ink">{label}</span>
                      {/* One value per line: an address never breaks mid-word on a phone. */}
                      <span className="block font-mono text-caption text-muted">{account.email}</span>
                      <span className="block font-mono text-caption text-muted">{account.password}</span>
                    </span>
                    <button
                      type="button"
                      className={buttonClasses("ghost", "sm", "shrink-0")}
                      aria-label={t("auth.demoFillLabel", { account: label })}
                      onClick={() => {
                        setEmail(account.email);
                        setPassword(account.password);
                      }}
                    >
                      {t("auth.demoFill")}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function RoleOption({
  value,
  selected,
  onSelect,
  icon,
  title,
  hint,
}: {
  value: ChosenRole;
  selected: ChosenRole;
  onSelect: (role: ChosenRole) => void;
  icon: ReactNode;
  title: string;
  hint: string;
}) {
  const checked = value === selected;
  return (
    <label
      className={cn(
        "flex cursor-pointer flex-col gap-2 rounded-lg border p-3.5 transition-colors duration-150",
        "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-focus",
        checked
          ? "border-brand bg-brand-tint shadow-[inset_0_0_0_1px_var(--color-brand)]"
          : "border-line-strong bg-surface hover:border-brand/40",
      )}
    >
      <input
        type="radio"
        name="role"
        value={value}
        checked={checked}
        onChange={() => onSelect(value)}
        className="sr-only"
      />
      <span className="flex items-center justify-between">
        <span
          className={cn(
            "grid size-9 place-items-center rounded-md transition-colors duration-150",
            checked ? "bg-brand text-white" : "bg-sunken text-muted",
          )}
        >
          {icon}
        </span>
        <span
          aria-hidden
          className={cn(
            "size-4 rounded-full border-2 transition-colors duration-150",
            checked ? "border-brand bg-brand shadow-[inset_0_0_0_2px_var(--color-surface)]" : "border-line-strong",
          )}
        />
      </span>
      <span className="font-semibold text-ink">{title}</span>
      <span className="hidden text-caption text-muted sm:block">{hint}</span>
    </label>
  );
}
