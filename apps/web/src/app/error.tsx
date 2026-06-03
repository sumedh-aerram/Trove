"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="space-y-4 rounded-xl border border-red-900/50 bg-red-950/30 p-6">
      <h2 className="text-lg font-semibold text-red-200">Something went wrong</h2>
      <p className="text-sm text-red-300/90">{error.message}</p>
      <button
        type="button"
        onClick={reset}
        className="rounded bg-slate-700 px-4 py-2 text-sm text-white hover:bg-slate-600"
      >
        Try again
      </button>
    </div>
  );
}
