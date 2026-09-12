export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" aria-hidden focusable={false}>
      <rect width="28" height="28" rx="8" fill="var(--color-brand)" />
      <path d="M5.5 18.5c2.6-5.2 5.4-7.8 8.5-7.8s5.9 2.6 8.5 7.8" stroke="#fff" strokeWidth="2.2" fill="none" strokeLinecap="round" />
      <path d="M9.5 18.5v-3.2M14 18.5v-6.4M18.5 18.5v-3.2" stroke="#fff" strokeWidth="1.9" strokeLinecap="round" />
    </svg>
  );
}
