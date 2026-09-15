"use client";

import { errorMessage, useI18n } from "@carebridge/i18n";
import type { LanguageCode, Message, Role } from "@carebridge/shared-types";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "./Button";
import { cn } from "./cn";
import { Alert } from "./Feedback";
import { Field, TextArea } from "./Field";

/**
 * Consultation messages, each kept in the words it was written in.
 *
 * Authorship is material, not just alignment: what the patient writes sits on
 * their own paper, what the doctor writes is inked. Both sides read the same
 * thread, so the two never swap materials depending on who is looking.
 */
export function MessageThread({
  messages,
  viewerRole,
  canSend,
  onSend,
  composeLanguage,
}: {
  messages: Message[];
  viewerRole: Role;
  canSend: boolean;
  onSend: (body: string) => Promise<void>;
  composeLanguage?: LanguageCode | null;
}) {
  const { t, formatDateTime } = useI18n();
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const listRef = useRef<HTMLOListElement>(null);

  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const body = draft.trim();
    if (!body || sending) return;
    setSending(true);
    setError(null);
    try {
      await onSend(body);
      setDraft("");
    } catch (err) {
      setError(err);
    } finally {
      setSending(false);
    }
  }

  const senderLabel = (role: Role) =>
    role === viewerRole ? t("messages.fromYou") : role === "doctor" ? t("messages.fromDoctor") : t("messages.fromPatient");

  return (
    <div className="flex flex-col gap-3">
      {messages.length === 0 ? (
        <p className="text-small text-muted">{t("messages.empty")}</p>
      ) : (
        <ol ref={listRef} tabIndex={0} aria-live="polite" className="flex max-h-[28rem] flex-col gap-3 overflow-y-auto pr-1">
          {messages.map((m) => {
            const mine = m.sender_role === viewerRole;
            const fromDoctor = m.sender_role === "doctor";
            return (
              <li key={m.id} className={cn("flex flex-col", mine ? "items-end" : "items-start")}>
                <div
                  lang={m.language ?? undefined}
                  className={cn(
                    "max-w-[85%] whitespace-pre-line rounded-md px-4 py-2.5",
                    fromDoctor ? "bg-ink text-white" : "border border-paper-line bg-paper text-paper-ink",
                  )}
                >
                  {m.body}
                </div>
                <p className="mt-1 text-caption text-muted">
                  {senderLabel(m.sender_role)} · <time dateTime={m.created_at}>{formatDateTime(m.created_at)}</time>
                </p>
              </li>
            );
          })}
        </ol>
      )}
      {canSend ? (
        <form onSubmit={submit} className="flex flex-col gap-2 border-t border-line pt-3">
          <Field label={t("messages.label")}>
            {(p) => (
              <TextArea
                {...p}
                rows={2}
                lang={composeLanguage ?? undefined}
                value={draft}
                maxLength={4000}
                placeholder={t("messages.placeholder")}
                onChange={(e) => setDraft(e.target.value)}
              />
            )}
          </Field>
          {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
          <div className="flex justify-end">
            <Button type="submit" disabled={!draft.trim() || sending}>
              {sending ? t("messages.sending") : t("actions.send")}
            </Button>
          </div>
        </form>
      ) : (
        <p className="rounded-md bg-sunken px-3 py-2 text-small text-muted">{t("messages.closed")}</p>
      )}
    </div>
  );
}
