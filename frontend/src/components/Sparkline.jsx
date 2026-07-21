// Minimal 12-week bar sparkline. Purely visual — driven by an integer array.
export default function Sparkline({ values = [], className = "", label }) {
  const max = Math.max(1, ...values);
  return (
    <div className={className} aria-label={label || "12-week commit activity"}>
      <div className="flex items-end gap-[3px] h-8">
        {Array.from({ length: 12 }).map((_, i) => {
          const v = values[i] ?? 0;
          const h = Math.round((v / max) * 100);
          return (
            <span
              data-testid={`sparkline-bar-${i}`}
              className="w-1.5 bg-foreground/70 rounded-[1px]"
              style={{ height: `${Math.max(6, h)}%`, opacity: v === 0 ? 0.25 : 0.9 }}
              key={`bar-${i}-${v}`}
            />
          );
        })}
      </div>
    </div>
  );
}
