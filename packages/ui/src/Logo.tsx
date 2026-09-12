/**
 * The Asclepius mark: a rod with information gathering along it.
 *
 * The rod is the instrument; the winding line is the patient's information being
 * ordered against it; the three nodes are the items that come out of it. Drawn in
 * `currentColor` so it works on the jade header, on paper and in a single colour.
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
      <path d="M14 3.25v21.5" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" />
      <path
        d="M9.1 7.6c3.3-2.7 9.8-1.2 9.8 2.4 0 3.9-9.8 3.9-9.8 7.8 0 3.6 6.5 5.1 9.8 2.4"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        opacity="0.85"
      />
      <circle cx="14" cy="4.1" r="1.5" fill="currentColor" />
      <circle cx="19.4" cy="14" r="1.15" fill="currentColor" opacity="0.55" />
      <circle cx="8.6" cy="14" r="1.15" fill="currentColor" opacity="0.55" />
    </svg>
  );
}
