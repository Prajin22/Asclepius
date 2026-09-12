import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cn } from "./cn";

export interface ControlProps {
  id: string;
  "aria-describedby"?: string;
  "aria-invalid"?: boolean;
}

/** Label + control + hint + error, wired for assistive technology. */
export function Field({
  label,
  hint,
  error,
  children,
  className,
}: {
  label: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  children: (props: ControlProps) => ReactNode;
  className?: string;
}) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-small font-semibold text-ink">
        {label}
      </label>
      {children({ id, "aria-describedby": describedBy, "aria-invalid": error ? true : undefined })}
      {hint ? (
        <p id={hintId} className="text-small text-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} role="alert" className="text-small font-medium text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

const controlBase =
  "w-full rounded-lg border border-line-strong bg-surface px-3.5 text-ink placeholder:text-subtle " +
  "aria-[invalid=true]:border-danger disabled:bg-sunken disabled:text-subtle";

export function TextInput({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(controlBase, "min-h-11", className)} {...props} />;
}

export function TextArea({ className, rows = 4, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea rows={rows} className={cn(controlBase, "py-2.5 leading-relaxed", className)} {...props} />;
}

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(controlBase, "min-h-11 pr-8", className)} {...props}>
      {children}
    </select>
  );
}

/**
 * Large, whole-row checkbox target. `card` stands on its own; `row` sits in a
 * list that already has a border, so it does not draw a box inside a box.
 */
export function Checkbox({
  label,
  description,
  checked,
  onChange,
  disabled,
  variant = "card",
}: {
  label: ReactNode;
  description?: ReactNode;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  variant?: "card" | "row";
}) {
  const id = useId();
  return (
    <label
      htmlFor={id}
      className={cn(
        "flex min-h-12 cursor-pointer items-start gap-3 rounded-lg px-3.5 py-3 transition-colors duration-150",
        variant === "card" &&
          (checked ? "border border-brand/40 bg-brand-soft" : "border border-line bg-surface hover:bg-sunken"),
        variant === "row" && (checked ? "bg-brand-tint" : "hover:bg-sunken"),
        disabled && "cursor-not-allowed opacity-60",
      )}
    >
      <input
        id={id}
        type="checkbox"
        className="mt-0.5 size-5 shrink-0 accent-[var(--color-brand)]"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="min-w-0">
        <span className="block font-medium text-ink">{label}</span>
        {description ? <span className="mt-0.5 block text-small text-muted">{description}</span> : null}
      </span>
    </label>
  );
}
