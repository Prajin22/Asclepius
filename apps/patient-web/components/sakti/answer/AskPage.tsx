"use client";

import { useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import { UI_LANGUAGES, languageInfo, type LanguageCode } from "@carebridge/shared-types";
import { Alert, Button, Field, PageHeader, Select, TextArea, TextInput, cn } from "@carebridge/ui";
import { Check, ChatCenteredText, GlobeHemisphereWest, MapPinArea } from "@phosphor-icons/react/dist/ssr";
import { useId, useState, type FormEvent } from "react";
import { EmptyPanel } from "../ui";
import { AnswerPanel, EscalationSuggestion } from ".";
import type { Jurisdiction } from "./types";

const LANES: { lane: Jurisdiction; icon: typeof MapPinArea }[] = [
  { lane: "india", icon: MapPinArea },
  { lane: "international", icon: GlobeHemisphereWest },
];

const today = () => new Date().toISOString().slice(0, 10);

/**
 * Ask Asclepius — the question form and where cited answers will appear. Phase
 * 3.5 builds the screen only: there is no answer service yet, so a question is
 * never sent anywhere and no answer, citation or legal text is shown. The
 * screen says so before and after the user presses the button.
 */
export function AskPage() {
  const { t, locale } = useI18n();
  const products = useQuery((a) => a.products.list());
  const [question, setQuestion] = useState("");
  const [product, setProduct] = useState("");
  const [asOf, setAsOf] = useState(today);
  const [lanes, setLanes] = useState<Set<Jurisdiction>>(new Set(["india", "international"]));
  const [language, setLanguage] = useState<LanguageCode>(
    (UI_LANGUAGES as readonly string[]).includes(locale) ? (locale as LanguageCode) : "en",
  );
  const [tried, setTried] = useState(false);
  const [held, setHeld] = useState(false);
  const jurisdictionId = useId();

  const questionError = tried && !question.trim() ? t("ask.validation.question") : undefined;
  const asOfError = tried && asOf > today() ? t("ask.validation.future") : undefined;

  function toggle(lane: Jurisdiction) {
    setLanes((current) => {
      const next = new Set(current);
      if (next.has(lane)) {
        // At least one lane is always chosen.
        if (next.size > 1) next.delete(lane);
      } else next.add(lane);
      return next;
    });
    setHeld(false);
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    setTried(true);
    if (!question.trim() || asOf > today()) return;
    // No answer service exists in this phase: the question is not sent anywhere.
    setHeld(true);
  }

  return (
    <>
      <PageHeader title={t("ask.title")} description={t("ask.description")} />
      <div className="flex flex-col gap-6">
        <Alert tone="info" title={t("ask.notEnabled.title")}>
          {t("ask.notEnabled.body")}
        </Alert>

        <form onSubmit={submit} noValidate className="grid gap-5 rounded-md border border-line bg-surface p-5 sm:p-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
          <Field label={t("ask.question")} hint={t("ask.questionHint")} error={questionError} className="lg:row-span-2">
            {(p) => (
              <TextArea
                {...p}
                rows={6}
                maxLength={2000}
                value={question}
                onChange={(e) => {
                  setQuestion(e.target.value);
                  setHeld(false);
                }}
              />
            )}
          </Field>

          <div className="flex flex-col gap-4">
            <Field label={t("ask.product")} hint={t("ask.productHint")}>
              {(p) => (
                <Select {...p} value={product} onChange={(e) => setProduct(e.target.value)}>
                  <option value="">{t("ask.noProduct")}</option>
                  {(products.data ?? []).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t("ask.asOf")} hint={t("ask.asOfHint")} error={asOfError}>
              {(p) => <TextInput {...p} type="date" max={today()} value={asOf} onChange={(e) => setAsOf(e.target.value)} />}
            </Field>
          </div>

          <div className="flex flex-col gap-4">
            <div role="group" aria-labelledby={jurisdictionId} className="flex flex-col gap-1.5">
              <p id={jurisdictionId} className="text-small font-semibold text-ink">
                {t("ask.jurisdiction")}
              </p>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-1">
                {LANES.map(({ lane, icon: Glyph }) => {
                  const on = lanes.has(lane);
                  return (
                    <button
                      key={lane}
                      type="button"
                      aria-pressed={on}
                      onClick={() => toggle(lane)}
                      className={cn(
                        "flex min-h-11 items-center justify-center gap-2 rounded-md border px-3 text-small font-semibold uppercase tracking-[0.04em] transition-colors duration-150",
                        on
                          ? lane === "india"
                            ? "border-lane-india bg-lane-india-soft text-lane-india"
                            : "border-lane-intl bg-lane-intl-soft text-lane-intl"
                          : "border-line-strong bg-surface text-muted hover:bg-sunken",
                      )}
                    >
                      {on ? <Check size={15} weight="bold" aria-hidden /> : <Glyph size={15} aria-hidden />}
                      {t(`ui.lane.${lane}`)}
                    </button>
                  );
                })}
              </div>
              <p className="text-small text-muted">{t("ask.jurisdictionHint")}</p>
            </div>
            <Field label={t("ask.language")} hint={t("ask.languageHint")}>
              {(p) => (
                <Select {...p} value={language} onChange={(e) => setLanguage(e.target.value as LanguageCode)}>
                  {UI_LANGUAGES.map((code) => (
                    <option key={code} value={code} lang={code}>
                      {languageInfo(code)?.nativeName}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>

          <div className="flex flex-col gap-3 border-t border-line pt-4 lg:col-span-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-small text-muted">{t("ask.notSentNote")}</p>
            <Button type="submit" className="shrink-0">
              <ChatCenteredText size={18} aria-hidden />
              {t("ask.submit")}
            </Button>
          </div>
          {held ? (
            <Alert tone="warning" title={t("ask.held.title")} className="lg:col-span-2">
              {t("ask.held.body")}
            </Alert>
          ) : null}
        </form>

        <div className={cn("grid gap-5", lanes.size > 1 ? "lg:grid-cols-2" : undefined)}>
          {LANES.filter(({ lane }) => lanes.has(lane)).map(({ lane }) => (
            <AnswerPanel
              key={lane}
              lane={lane}
              empty={
                <EmptyPanel icon={ChatCenteredText} title={t("ask.empty.title")} className="flex-1 py-8">
                  {t("ask.empty.body")}
                </EmptyPanel>
              }
            />
          ))}
        </div>

        <section aria-labelledby="ask-how" className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-start">
          <div className="rounded-md border border-line bg-surface p-5 sm:p-6">
            <h2 id="ask-how" className="text-subheading text-ink">
              {t("ask.how.title")}
            </h2>
            <ul className="mt-3 flex flex-col gap-2.5">
              {(["one", "two", "three"] as const).map((k) => (
                <li key={k} className="flex gap-2.5 text-ink">
                  <Check size={18} weight="bold" aria-hidden className="mt-0.5 shrink-0 text-brand" />
                  {t(`pages.ask.points.${k}`)}
                </li>
              ))}
            </ul>
          </div>
          <EscalationSuggestion />
        </section>
      </div>
    </>
  );
}
