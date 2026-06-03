export function ScoreBadge({
  label,
  value,
  invert = false,
}: {
  label: string;
  value?: number;
  invert?: boolean;
}) {
  const v = value ?? 0;
  const color = invert
    ? v > 50
      ? "text-red-400"
      : "text-emerald-400"
    : v >= 70
      ? "text-emerald-400"
      : v >= 45
        ? "text-amber-400"
        : "text-slate-400";

  return (
    <span className={`text-xs ${color}`}>
      {label}: {Math.round(v)}
    </span>
  );
}
