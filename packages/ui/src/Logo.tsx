/**
 * The Asclepius mark: the rod, drawn in the fold language.
 *
 * A square sheet, one solid crease as the rod, a pleated line winding around it,
 * and the dot that marks whatever is waiting. Drawn in `currentColor` so it works
 * on ink, on the vermilion sheet and on paper, and it survives at 16px.
 */
export function Logo({ size = 28, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 28 28"
      fill="none"
      className={className}
      aria-hidden
      focusable={false}
    >
      <rect x="4.2" y="4.2" width="19.6" height="19.6" rx="0.6" stroke="currentColor" strokeWidth="1.2" opacity="0.4" />
      <path d="M14 7.4V23" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path
        d="M9.6 10.6 18.4 12.9 9.6 15.5 18.4 18 9.6 20.6"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.62"
      />
      <circle cx="14" cy="5.6" r="1.9" fill="currentColor" />
    </svg>
  );
}
