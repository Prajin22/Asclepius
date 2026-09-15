import type { ButtonHTMLAttributes } from "react";
import { cn } from "./cn";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "onDark";
export type ButtonSize = "sm" | "md" | "lg";

/**
 * Colour is spent in one place per screen: the sheet, and the primary action.
 * Everything else is paper and ink.
 */
const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-brand text-white shadow-xs hover:bg-brand-strong disabled:bg-line disabled:text-subtle disabled:shadow-none",
  secondary:
    "border border-line-strong bg-surface text-ink hover:border-brand/50 hover:bg-brand-tint disabled:text-subtle",
  ghost: "text-brand-strong hover:bg-brand-soft disabled:text-subtle",
  danger: "border border-danger/35 bg-surface text-danger hover:bg-danger-soft disabled:text-subtle",
  // For the ink chrome of the clinician workspace, where a paper button would punch a hole.
  onDark: "border border-white/25 bg-white/10 text-white hover:bg-white/20 disabled:text-white/50",
};

const sizes: Record<ButtonSize, string> = {
  // On a phone no target is under 44px; the compact height is for pointers.
  sm: "min-h-11 gap-1.5 px-3 text-small sm:min-h-9",
  md: "min-h-11 gap-2 px-4 text-body",
  lg: "min-h-13 gap-2 px-6 text-body-lg",
};

/** Class string for links styled as buttons (framework-agnostic). */
export function buttonClasses(variant: ButtonVariant = "primary", size: ButtonSize = "md", className?: string) {
  return cn(
    "inline-flex items-center justify-center rounded-md font-semibold",
    // The press is felt, not watched: 1px down, no bounce.
    "transition-[background-color,border-color,color,box-shadow,transform] duration-150 ease-out-soft active:translate-y-px",
    "disabled:cursor-not-allowed disabled:active:translate-y-0",
    variants[variant],
    sizes[size],
    className,
  );
}

export function Button({
  variant = "primary",
  size = "md",
  className,
  type = "button",
  loading = false,
  disabled,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Shows progress in place and blocks repeat submits. */
  loading?: boolean;
}) {
  return (
    <button
      type={type}
      className={buttonClasses(variant, size, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? (
        <span
          aria-hidden
          className="size-4 animate-spin rounded-full border-2 border-current border-r-transparent opacity-70"
        />
      ) : null}
      {children}
    </button>
  );
}
