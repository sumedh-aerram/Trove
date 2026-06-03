export function TagPill({ label }: { label: string }) {
  return (
    <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
      {label}
    </span>
  );
}
