"use client";

import { useApi, useQuery } from "@carebridge/api-client/react";
import { errorMessage, useI18n } from "@carebridge/i18n";
import type { ClassificationSession, ClassifierNode } from "@carebridge/shared-types";
import { Alert, Badge, Button, Card, ErrorState, Field, PageHeader, SkeletonCard, TextArea, cn } from "@carebridge/ui";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { ArrowLeftIcon } from "@/components/icons";
import { STATUS_TONE } from "./ClassifyStart";
import { ReferenceList } from "./ReferenceList";

const OPEN = new Set(["incomplete", "requires_information", "determined"]);

/**
 * One classification session. The questions, their order and the result all
 * come from the classifier tree the session started on; this screen only shows
 * them and sends the user's choices back. It never decides anything itself.
 */
export function ClassificationFlow({ id }: { id: string }) {
  const api = useApi();
  const router = useRouter();
  const { t, formatDateTime } = useI18n();
  const q = useQuery((a) => a.classifier.session(id), [id]);
  const session = q.data;
  const tree = useQuery(
    (a) => (session ? a.classifier.tree(session.tree_version) : Promise.resolve(null)),
    [session?.tree_version],
  );
  const [editing, setEditing] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  if (q.error && !session) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!session || !tree.data) return <SkeletonCard />;
  const nodes = Object.fromEntries(tree.data.nodes.map((n) => [n.id, n]));
  const open = OPEN.has(session.status);

  async function act(run: () => Promise<ClassificationSession>) {
    setBusy(true);
    setError(null);
    try {
      q.setData(await run());
      setEditing(null);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  async function restart() {
    setBusy(true);
    setError(null);
    try {
      const next = await api.classifier.restart(id);
      router.push(`/classify/${next.id}`);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }
  const respond = (nodeId: string, choice: string) => act(() => api.classifier.respond(id, nodeId, choice));
  const current = session.status === "incomplete" && session.current_node_id ? nodes[session.current_node_id] : null;
  const stopped = session.status === "requires_information" && session.current_node_id ? nodes[session.current_node_id] : null;
  const outcome = session.latest_outcome;
  const showResult = Boolean(session.category && outcome?.kind === "determined");

  return (
    <>
      <PageHeader
        back={
          <Link href="/classify" className="inline-flex items-center gap-1.5 font-medium text-brand-strong hover:underline">
            <ArrowLeftIcon aria-hidden />
            {t("classifier.session.back")}
          </Link>
        }
        title={t("classifier.session.title", { product: session.product_name })}
        description={t("classifier.session.tree", { version: session.tree_version })}
        actions={<Badge tone={STATUS_TONE[session.status]}>{t(`classifier.status.${session.status}`)}</Badge>}
      />
      <div className="flex max-w-3xl flex-col gap-5">
        {session.status === "superseded" ? <Alert tone="info">{t("classifier.session.superseded")}</Alert> : null}
        {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}

        {session.path.length ? (
          <Card aria-labelledby="answered">
            <h2 id="answered" className="text-subheading text-ink">
              {t("classifier.session.answered")}
            </h2>
            <ol className="mt-3 flex flex-col divide-y divide-line">
              {session.path.map((step) => {
                const node = nodes[step.node_id];
                const choice = node.choices.find((c) => c.id === step.choice);
                return (
                  <li key={step.node_id} className="py-3 first:pt-0 last:pb-0">
                    <p className="text-small text-muted">{t(node.question_key)}</p>
                    {editing === step.node_id ? (
                      <ChoiceForm
                        node={node}
                        initial={step.choice}
                        busy={busy}
                        onSubmit={(c) => respond(node.id, c)}
                        extra={
                          <Button type="button" variant="ghost" onClick={() => setEditing(null)} disabled={busy}>
                            {t("classifier.session.cancelChange")}
                          </Button>
                        }
                      />
                    ) : (
                      <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
                        <span className={cn("font-semibold", step.choice === "unknown" ? "text-warning" : "text-ink")}>
                          {choice ? t(choice.label_key) : step.choice}
                        </span>
                        {open ? (
                          <Button variant="ghost" size="sm" onClick={() => setEditing(step.node_id)} disabled={busy || editing !== null}>
                            {t("classifier.session.change")}
                          </Button>
                        ) : null}
                      </div>
                    )}
                  </li>
                );
              })}
            </ol>
          </Card>
        ) : null}

        {current && editing === null ? (
          <Card aria-labelledby="question">
            <ChoiceForm
              node={current}
              busy={busy}
              titleId="question"
              onSubmit={(c) => respond(current.id, c)}
              context={<ProductContext node={current} snapshot={session.product_snapshot} />}
            />
          </Card>
        ) : null}

        {stopped ? (
          <Alert tone="warning" title={t("classifier.session.stopTitle")}>
            <div className="flex flex-col gap-1.5">
              <p>{t("classifier.session.stopMissing", { missing: t(stopped.missing_key) })}</p>
              <p>{t("classifier.session.stopWhy", { why: t(stopped.why_key) })}</p>
              <p>{t("classifier.session.stopBody")}</p>
            </div>
          </Alert>
        ) : null}

        {showResult && outcome && session.category ? (
          <Card aria-labelledby="result">
            <h2 id="result" className="text-subheading text-ink">
              {t("classifier.session.resultTitle")}
            </h2>
            <dl className="mt-3 flex flex-col divide-y divide-line">
              <Row label={t("classifier.session.classification")}>
                <span className="text-heading text-ink">{t(`classifier.category.${session.category}`)}</span>
              </Row>
              <Row label={t("classifier.session.status")}>{t(`classifier.status.${session.status}`)}</Row>
              <Row label={t("classifier.session.confirmation")}>
                {session.status === "user_confirmed" && session.decided_at
                  ? t("classifier.session.confirmedOn", { date: formatDateTime(session.decided_at) })
                  : session.status === "user_rejected" && session.decided_at
                    ? t("classifier.session.rejectedOn", { date: formatDateTime(session.decided_at) })
                    : t("classifier.session.awaiting")}
              </Row>
              <Row label={t("classifier.session.references")}>
                <ReferenceList slots={session.references} />
              </Row>
            </dl>
            <p className="mt-4 border-t border-line pt-3 text-small text-muted">{t("classifier.session.resultNote")}</p>
            {session.status === "determined" ? (
              <Decision
                busy={busy}
                onConfirm={() => act(() => api.classifier.confirm(id, outcome.id))}
                onReject={(reason) => act(() => api.classifier.reject(id, outcome.id, reason))}
              />
            ) : null}
            {session.status === "user_rejected" ? <p className="mt-4 text-ink">{t("classifier.session.rejectedNote")}</p> : null}
          </Card>
        ) : null}

        {session.status !== "superseded" ? (
          <div>
            <Button variant="secondary" onClick={restart} disabled={busy}>
              {busy ? t("classifier.session.restarting") : t("classifier.session.restart")}
            </Button>
          </div>
        ) : null}

        {session.outcomes.length > 1 ? (
          <section aria-labelledby="outcomes" className="flex flex-col gap-2">
            <h2 id="outcomes" className="text-subheading text-ink">
              {t("classifier.session.history")}
            </h2>
            <ol className="flex flex-col gap-1 text-small text-muted">
              {session.outcomes.map((o) => (
                <li key={o.id}>
                  {t("classifier.session.historyItem", {
                    number: o.sequence,
                    result: o.category ? t(`classifier.category.${o.category}`) : t("classifier.session.stoppedAt"),
                  })}{" "}
                  · {formatDateTime(o.created_at)}
                </li>
              ))}
            </ol>
          </section>
        ) : null}
      </div>
    </>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 py-3 first:pt-0 sm:grid-cols-[10rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-small font-semibold text-muted">{label}</dt>
      <dd className="min-w-0 text-ink">{children}</dd>
    </div>
  );
}

/** One question's choices as radio buttons. "I don't know" is always offered. */
function ChoiceForm({
  node,
  initial,
  busy,
  titleId,
  onSubmit,
  context,
  extra,
}: {
  node: ClassifierNode;
  initial?: string;
  busy: boolean;
  titleId?: string;
  onSubmit: (choice: string) => void;
  context?: ReactNode;
  extra?: ReactNode;
}) {
  const { t } = useI18n();
  const [choice, setChoice] = useState<string | null>(initial ?? null);
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (choice) onSubmit(choice);
      }}
    >
      <fieldset className="flex flex-col gap-2">
        <legend id={titleId} className="text-subheading text-ink">
          {t(node.question_key)}
        </legend>
        <p className="text-small text-muted">{t(node.help_key)}</p>
        {context}
        {node.choices.map((c) => (
          <label
            key={c.id}
            className={cn(
              "flex min-h-12 cursor-pointer items-center gap-3 rounded-md border px-3.5 py-3",
              choice === c.id ? "border-brand/45 bg-brand-soft" : "border-line bg-surface hover:bg-sunken",
            )}
          >
            <input
              type="radio"
              name={`choice-${node.id}`}
              value={c.id}
              checked={choice === c.id}
              onChange={() => setChoice(c.id)}
              className="size-5 accent-[var(--color-brand)]"
            />
            <span className="font-medium text-ink">{t(c.label_key)}</span>
          </label>
        ))}
      </fieldset>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={busy || !choice}>
          {busy ? t("classifier.session.saving") : t("classifier.session.continue")}
        </Button>
        {extra}
      </div>
    </form>
  );
}

/** What the user wrote about the product that bears on this question — their words, shown back to them. */
function ProductContext({ node, snapshot }: { node: ClassifierNode; snapshot: Record<string, unknown> }) {
  const { t } = useI18n();
  if (!node.context_fields.length) return null;
  const show = (field: string, value: unknown): string | null => {
    if (value == null || value === "") return null;
    if (field === "administration_route") return t(`product.route.${String(value)}`);
    if (field === "ingredients" && Array.isArray(value)) {
      return value.map((i) => (i as { name?: string }).name).filter(Boolean).join(", ") || null;
    }
    if (Array.isArray(value)) return value.length ? value.join(", ") : null;
    return String(value);
  };
  return (
    <div className="rounded-md border border-line bg-sunken px-3.5 py-3">
      <p className="text-caption font-semibold uppercase text-subtle">{t("classifier.session.context")}</p>
      <dl className="mt-1.5 flex flex-col gap-1.5">
        {node.context_fields.map((field) => {
          const value = show(field, snapshot[field]);
          return (
            <div key={field}>
              <dt className="text-small font-semibold text-muted">{t(`product.field.${field}`)}</dt>
              <dd className="text-small text-ink">{value ?? t("classifier.session.noContext")}</dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}

function Decision({ busy, onConfirm, onReject }: { busy: boolean; onConfirm: () => void; onReject: (reason: string) => void }) {
  const { t } = useI18n();
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  return rejecting ? (
    <div className="mt-4 flex flex-col gap-3">
      <Field label={t("classifier.session.rejectReason")}>
        {(p) => <TextArea {...p} rows={2} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />}
      </Field>
      <div className="flex flex-wrap gap-2">
        <Button variant="danger" onClick={() => onReject(reason.trim())} disabled={busy}>
          {t("classifier.session.confirmReject")}
        </Button>
        <Button variant="ghost" onClick={() => setRejecting(false)} disabled={busy}>
          {t("classifier.session.cancel")}
        </Button>
      </div>
    </div>
  ) : (
    <div className="mt-4 flex flex-wrap gap-2">
      <Button onClick={onConfirm} disabled={busy}>
        {t("classifier.session.confirm")}
      </Button>
      <Button variant="secondary" onClick={() => setRejecting(true)} disabled={busy}>
        {t("classifier.session.reject")}
      </Button>
    </div>
  );
}
