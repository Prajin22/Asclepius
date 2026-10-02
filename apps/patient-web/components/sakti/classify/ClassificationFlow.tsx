"use client";

import { useApi, useQuery } from "@carebridge/api-client/react";
import { errorMessage, useI18n } from "@carebridge/i18n";
import type { ClassificationSession, ClassificationStep, ClassifierNode } from "@carebridge/shared-types";
import { Alert, Button, ErrorState, Field, PageHeader, SkeletonCard, TextArea, buttonClasses, cn } from "@carebridge/ui";
import { ArrowLeft, CaretDown, CheckCircle, Question, SealCheck } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { ArrowLeftIcon } from "@/components/icons";
import { ChoiceCard, InfoOnly, StepProgress } from "../ui";
import { ReferenceList } from "./ReferenceList";
import { SessionBadge } from "./status";

const OPEN = new Set(["incomplete", "requires_information", "determined"]);

/**
 * One classification session, as a guided flow. The questions, their order and
 * the result all come from the classifier tree the session started on; this
 * screen only shows them and sends the user's choices back. It never decides
 * anything itself, never suggests a category after "I don't know", and a
 * result stays a proposal until the user confirms it.
 */
export function ClassificationFlow({ id }: { id: string }) {
  const api = useApi();
  const router = useRouter();
  const { t } = useI18n();
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
  const total = tree.data.nodes.length;
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
  const editingIndex = editing ? session.path.findIndex((s) => s.node_id === editing) : -1;
  const lastStep = session.path[session.path.length - 1];

  const answers = (title: string) => (
    <Answers
      title={title}
      path={session.path}
      nodes={nodes}
      open={open}
      busy={busy}
      editing={editing}
      onChange={(nodeId) => setEditing(nodeId)}
    />
  );

  let main: ReactNode;
  if (editing && editingIndex >= 0) {
    const node = nodes[editing];
    main = (
      <QuestionCard
        key={`edit-${editing}`}
        node={node}
        step={editingIndex + 1}
        total={total}
        initial={session.path[editingIndex].choice}
        busy={busy}
        snapshot={session.product_snapshot}
        note={t("classifier.flow.changingNote")}
        onSubmit={(c) => respond(node.id, c)}
        secondary={
          <Button variant="ghost" onClick={() => setEditing(null)} disabled={busy}>
            {t("classifier.session.cancelChange")}
          </Button>
        }
      />
    );
  } else if (current) {
    main = (
      <QuestionCard
        key={current.id}
        node={current}
        step={session.path.length + 1}
        total={total}
        busy={busy}
        snapshot={session.product_snapshot}
        onSubmit={(c) => respond(current.id, c)}
        secondary={
          lastStep ? (
            <Button variant="secondary" onClick={() => setEditing(lastStep.node_id)} disabled={busy}>
              <ArrowLeft size={16} aria-hidden />
              {t("classifier.flow.back")}
            </Button>
          ) : null
        }
      />
    );
  } else if (stopped) {
    main = <NeedsInformation node={stopped} productId={session.product_id} onChange={() => setEditing(stopped.id)} busy={busy} />;
  } else if (showResult && outcome && session.category) {
    main = (
      <Result
        session={session}
        busy={busy}
        how={answers(t("classifier.result.how"))}
        onConfirm={() => act(() => api.classifier.confirm(id, outcome.id))}
        onReject={(reason) => act(() => api.classifier.reject(id, outcome.id, reason))}
        onChangeAnswer={() => {
          // The answers, each with its own Change button, are listed just below the result.
          const list = document.getElementById("answered");
          list?.scrollIntoView?.({ block: "start" });
          list?.focus();
        }}
      />
    );
  }

  const twoColumn = !showResult || editing !== null;

  return (
    <>
      <PageHeader
        back={
          <Link
            href={`/my-product/${session.product_id}`}
            className="inline-flex items-center gap-1.5 font-medium text-brand-strong hover:underline"
          >
            <ArrowLeftIcon aria-hidden />
            {session.product_name}
          </Link>
        }
        title={t("classifier.session.title", { product: session.product_name })}
        description={t("classifier.session.tree", { version: session.tree_version })}
        actions={<SessionBadge status={session.status} />}
      />

      <div className={cn("grid gap-6", twoColumn ? "lg:grid-cols-[minmax(0,1fr)_20rem]" : "max-w-3xl")}>
        <div className="flex min-w-0 flex-col gap-5">
          {session.status === "superseded" ? <Alert tone="info">{t("classifier.session.superseded")}</Alert> : null}
          {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
          {main}
        </div>

        <aside className="flex flex-col gap-4">
          {twoColumn && session.path.length ? answers(t("classifier.session.answered")) : null}
          {session.status !== "superseded" ? (
            <div className="rounded-md border border-line bg-surface p-4">
              <p className="text-small text-muted">{t("classifier.flow.restartHint")}</p>
              <Button variant="secondary" size="sm" onClick={restart} disabled={busy} className="mt-3">
                {busy ? t("classifier.session.restarting") : t("classifier.session.restart")}
              </Button>
            </div>
          ) : null}
          {session.outcomes.length > 1 ? <Outcomes session={session} /> : null}
        </aside>
      </div>
    </>
  );
}

/** One question as answer cards. "I don't know" is always offered, and set apart. */
function QuestionCard({
  node,
  step,
  total,
  initial,
  busy,
  snapshot,
  note,
  onSubmit,
  secondary,
}: {
  node: ClassifierNode;
  step: number;
  total: number;
  initial?: string;
  busy: boolean;
  snapshot: Record<string, unknown>;
  note?: string;
  onSubmit: (choice: string) => void;
  secondary?: ReactNode;
}) {
  const { t } = useI18n();
  const [choice, setChoice] = useState<string | null>(initial ?? null);
  const legendId = `question-${node.id}`;
  return (
    <form
      className="flex flex-col gap-5 rounded-md border border-line bg-surface p-5 motion-safe:animate-rise sm:p-6"
      onSubmit={(e) => {
        e.preventDefault();
        if (choice) onSubmit(choice);
      }}
    >
      <div>
        <StepProgress step={step} total={total} label={t("classifier.flow.step", { step, total })} />
        <p className="mt-1.5 text-caption text-subtle">{t("classifier.flow.stepNote")}</p>
      </div>
      <fieldset className="flex flex-col gap-3">
        <legend id={legendId} className="text-heading text-ink">
          {t(node.question_key)}
        </legend>
        <div className="mt-1 rounded-md bg-brand-tint px-3.5 py-2.5">
          <p className="text-caption font-semibold uppercase tracking-wide text-brand-strong">{t("classifier.flow.whyAsk")}</p>
          <p className="mt-0.5 text-small text-ink">{t(node.help_key)}</p>
        </div>
        {note ? <Alert tone="info">{note}</Alert> : null}
        <ProductContext node={node} snapshot={snapshot} />
        <div className="mt-1 flex flex-col gap-2.5">
          {node.choices.map((c) => (
            <ChoiceCard
              key={c.id}
              name={`choice-${node.id}`}
              value={c.id}
              checked={choice === c.id}
              onChange={setChoice}
              title={t(c.label_key)}
              hint={c.id === "unknown" ? t("classifier.flow.unknownHint") : t(`classifier.v1.${node.id}.hint.${c.id}`)}
              kind={c.id === "unknown" ? "unknown" : "answer"}
            />
          ))}
        </div>
      </fieldset>
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-4">
        <div>{secondary}</div>
        <Button type="submit" disabled={busy || !choice}>
          {busy ? t("classifier.session.saving") : t("classifier.session.continue")}
        </Button>
      </div>
    </form>
  );
}

/** What the user wrote about the product that bears on this question — their words, shown back to them. */
function ProductContext({ node, snapshot }: { node: ClassifierNode; snapshot: Record<string, unknown> }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(true);
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
  const panelId = `context-${node.id}`;
  return (
    <div className="rounded-md border border-line bg-sunken">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className="flex min-h-11 w-full items-center justify-between gap-2 px-3.5 text-left text-small font-semibold text-muted"
      >
        {t("classifier.session.context")}
        <CaretDown size={14} aria-hidden className={cn("transition-transform duration-150", open ? "rotate-180" : undefined)} />
      </button>
      {open ? (
        <dl id={panelId} className="flex flex-col gap-2 border-t border-line px-3.5 py-3">
          {node.context_fields.map((field) => {
            const value = show(field, snapshot[field]);
            return (
              <div key={field}>
                <dt className="text-caption font-semibold text-subtle">{t(`product.field.${field}`)}</dt>
                <dd className={cn("text-small", value ? "text-ink" : "text-subtle")}>{value ?? t("classifier.session.noContext")}</dd>
              </div>
            );
          })}
        </dl>
      ) : null}
    </div>
  );
}

/** The answers given so far, each changeable while the session is open. */
function Answers({
  title,
  path,
  nodes,
  open,
  busy,
  editing,
  onChange,
}: {
  title: string;
  path: ClassificationStep[];
  nodes: Record<string, ClassifierNode>;
  open: boolean;
  busy: boolean;
  editing: string | null;
  onChange: (nodeId: string) => void;
}) {
  const { t } = useI18n();
  return (
    <section aria-labelledby="answered" className="rounded-md border border-line bg-surface p-4 sm:p-5">
      <h2 id="answered" tabIndex={-1} className="text-subheading text-ink outline-none">
        {title}
      </h2>
      <ol className="mt-3 flex flex-col divide-y divide-line">
        {path.map((step, i) => {
          const node = nodes[step.node_id];
          const choice = node.choices.find((c) => c.id === step.choice);
          const unknown = step.choice === "unknown";
          return (
            <li key={step.node_id} className={cn("flex gap-3 py-3 first:pt-0 last:pb-0", editing === step.node_id && "opacity-60")}>
              <span aria-hidden className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-sunken text-caption font-bold text-muted">
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-small text-muted">{t(`classifier.v1.${step.node_id}.short`)}</p>
                <p className={cn("font-semibold", unknown ? "text-muted" : "text-ink")}>
                  {unknown ? <Question size={14} weight="bold" aria-hidden className="mr-1 inline align-[-2px]" /> : null}
                  {choice ? t(choice.label_key) : step.choice}
                </p>
              </div>
              {open && editing === null ? (
                <Button variant="ghost" size="sm" onClick={() => onChange(step.node_id)} disabled={busy} className="shrink-0">
                  {t("classifier.session.change")}
                  <span className="sr-only"> — {t(`classifier.v1.${step.node_id}.short`)}</span>
                </Button>
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/** "I don't know" stops the classifier: what is missing, why it matters, and that nothing was assumed. No category. */
function NeedsInformation({
  node,
  productId,
  onChange,
  busy,
}: {
  node: ClassifierNode;
  productId: string;
  onChange: () => void;
  busy: boolean;
}) {
  const { t } = useI18n();
  return (
    <section
      aria-labelledby="unknown-title"
      className="rounded-md border border-dashed border-line-strong bg-surface p-5 motion-safe:animate-rise sm:p-6"
    >
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-sunken text-ink">
          <Question size={22} weight="bold" aria-hidden />
        </span>
        <div className="min-w-0">
          <h2 id="unknown-title" className="text-heading text-ink">
            {t("classifier.unknown.title")}
          </h2>
          <p className="mt-1 text-muted">{t("classifier.unknown.lead")}</p>
        </div>
      </div>
      <dl className="mt-5 grid gap-4 sm:grid-cols-2">
        <div className="rounded-md bg-sunken p-4">
          <dt className="text-caption font-semibold uppercase tracking-wide text-muted">{t("classifier.unknown.missing")}</dt>
          <dd className="mt-1 text-ink">{t(node.missing_key)}</dd>
        </div>
        <div className="rounded-md bg-sunken p-4">
          <dt className="text-caption font-semibold uppercase tracking-wide text-muted">{t("classifier.unknown.why")}</dt>
          <dd className="mt-1 text-ink">{t(node.why_key)}</dd>
        </div>
      </dl>
      <p className="mt-4 flex items-start gap-2 font-medium text-ink">
        <CheckCircle size={18} weight="bold" aria-hidden className="mt-0.5 shrink-0 text-brand" />
        {t("classifier.unknown.assumed")}
      </p>
      <div className="mt-5 flex flex-wrap gap-2 border-t border-line pt-4">
        <Link href={`/my-product/${productId}/edit`} className={buttonClasses("primary", "md")}>
          {t("classifier.unknown.review")}
        </Link>
        <Link href={`/my-product/${productId}`} className={buttonClasses("secondary", "md")}>
          {t("classifier.unknown.return")}
        </Link>
        <Button variant="ghost" onClick={onChange} disabled={busy}>
          {t("classifier.unknown.change")}
        </Button>
      </div>
    </section>
  );
}

/** The category the user's answers lead to: a proposal, explained, waiting for the user's own confirmation. */
function Result({
  session,
  busy,
  how,
  onConfirm,
  onReject,
  onChangeAnswer,
}: {
  session: ClassificationSession;
  busy: boolean;
  how: ReactNode;
  onConfirm: () => void;
  onReject: (reason: string) => void;
  onChangeAnswer: () => void;
}) {
  const { t, formatDateTime } = useI18n();
  const [changing, setChanging] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const confirmed = session.status === "user_confirmed";
  const rejected = session.status === "user_rejected";

  return (
    <>
      <section
        aria-labelledby="result-title"
        className={cn(
          "rounded-md border bg-surface p-5 motion-safe:animate-rise sm:p-7",
          confirmed ? "border-success/40" : "border-line",
        )}
      >
        <p className="flex items-center gap-2 text-small font-semibold text-brand-strong">
          {confirmed ? (
            <SealCheck size={18} weight="fill" aria-hidden className="text-success" />
          ) : (
            <CheckCircle size={18} weight="fill" aria-hidden />
          )}
          <span id="result-title">{t("classifier.result.complete")}</span>
        </p>
        <p className="mt-3 text-title text-ink">{t(`classifier.category.${session.category}`)}</p>
        <p className="mt-2 text-muted">
          {confirmed && session.decided_at
            ? t("classifier.session.confirmedOn", { date: formatDateTime(session.decided_at) })
            : rejected && session.decided_at
              ? t("classifier.session.rejectedOn", { date: formatDateTime(session.decided_at) })
              : t("classifier.result.determined")}
        </p>
        <p className="mt-3 flex items-center gap-2 text-small font-medium text-ink">
          <CheckCircle size={16} weight="bold" aria-hidden className="text-success" />
          {t("classifier.result.allAnswered")}
        </p>

        <div className="mt-6 rounded-md border border-line bg-sunken/60 p-4">
          <h2 className="text-small font-semibold text-ink">{t("classifier.result.references")}</h2>
          <div className="mt-3">
            <ReferenceList slots={session.references} />
          </div>
        </div>

        <p className="mt-5 text-small text-muted">{t("classifier.session.resultNote")}</p>

        {session.status === "determined" ? (
          <div className="mt-6 border-t border-line pt-5">
            <p className="text-subheading text-ink">{t("classifier.result.question")}</p>
            <p className="mt-0.5 text-small text-muted">{t("classifier.session.awaiting")}</p>
            {rejecting ? (
              <div className="mt-4 flex flex-col gap-3">
                <Field label={t("classifier.session.rejectReason")}>
                  {(p) => <TextArea {...p} rows={2} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />}
                </Field>
                <p className="text-small text-muted">{t("classifier.result.rejectNote")}</p>
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
                  <SealCheck size={18} aria-hidden />
                  {t("classifier.session.confirm")}
                </Button>
                <Button variant="secondary" onClick={() => setChanging((v) => !v)} aria-expanded={changing} disabled={busy}>
                  {t("classifier.result.change")}
                </Button>
              </div>
            )}
            {changing && !rejecting ? (
              <div className="mt-4 rounded-md border border-line bg-sunken/60 p-4">
                <p className="font-semibold text-ink">{t("classifier.result.changeTitle")}</p>
                <ul className="mt-2 flex flex-col gap-1">
                  <li>
                    <button type="button" onClick={onChangeAnswer} className="min-h-11 text-left font-medium text-brand-strong hover:underline">
                      {t("classifier.result.changeAnswer")}
                    </button>
                  </li>
                  <li>
                    <Link
                      href={`/my-product/${session.product_id}/edit`}
                      className="inline-flex min-h-11 items-center font-medium text-brand-strong hover:underline"
                    >
                      {t("classifier.result.editProduct")}
                    </Link>
                  </li>
                  <li>
                    <button
                      type="button"
                      onClick={() => setRejecting(true)}
                      className="min-h-11 text-left font-medium text-danger hover:underline"
                    >
                      {t("classifier.session.reject")}
                    </button>
                  </li>
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}
        {rejected ? <p className="mt-5 border-t border-line pt-4 text-ink">{t("classifier.session.rejectedNote")}</p> : null}
        <InfoOnly className="mt-5 border-t border-line pt-4" />
      </section>
      {how}
    </>
  );
}

function Outcomes({ session }: { session: ClassificationSession }) {
  const { t, formatDateTime } = useI18n();
  return (
    <section aria-labelledby="outcomes" className="rounded-md border border-line bg-surface p-4">
      <h2 id="outcomes" className="text-small font-semibold text-ink">
        {t("classifier.session.history")}
      </h2>
      <ol className="mt-2 flex flex-col gap-1.5 text-small text-muted">
        {session.outcomes.map((o) => (
          <li key={o.id}>
            {t("classifier.session.historyItem", {
              number: o.sequence,
              result: o.category ? t(`classifier.category.${o.category}`) : t("classifier.session.stoppedAt"),
            })}
            <span className="block text-caption text-subtle">{formatDateTime(o.created_at)}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
