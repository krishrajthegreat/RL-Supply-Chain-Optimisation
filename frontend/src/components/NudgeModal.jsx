export default function NudgeModal({ nudge, onAction }) {
  if (!nudge) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={() => onAction('dismiss')}>
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Modal */}
      <div className="relative glass-panel p-6 max-w-md w-full mx-4 animate-fade-in"
        onClick={e => e.stopPropagation()}>
        {/* Warning icon */}
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-red-500/20 flex items-center justify-center text-xl">
            ⚠️
          </div>
          <div>
            <h3 className="text-base font-bold text-white">{nudge.title}</h3>
            <p className="text-[10px] text-[var(--color-nexus-muted)] uppercase tracking-wider">Behavioural Nudge</p>
          </div>
        </div>

        {/* Message */}
        <p className="text-sm text-[var(--color-nexus-muted)] leading-relaxed mb-5 max-h-32 overflow-y-auto">
          {nudge.message}
        </p>

        {/* Divider */}
        <div className="h-px bg-[var(--color-nexus-border)] mb-4" />

        {/* Recommended action highlight */}
        <p className="text-[10px] text-[var(--color-nexus-muted)] uppercase tracking-wider mb-3">Recommended Actions</p>

        {/* Action buttons */}
        <div className="flex flex-col gap-2">
          {nudge.options.map((opt, i) => {
            const isPrimary = i === 0;
            const isDismiss = opt.action === 'dismiss';

            return (
              <button key={opt.action}
                onClick={() => onAction(opt.action)}
                className={`px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
                  isPrimary
                    ? 'bg-gradient-to-r from-cyan-600 to-blue-600 text-white hover:from-cyan-500 hover:to-blue-500 shadow-lg shadow-cyan-500/20'
                    : isDismiss
                      ? 'bg-transparent text-[var(--color-nexus-muted)] hover:text-white hover:bg-white/[0.05] border border-[var(--color-nexus-border)]'
                      : 'bg-[var(--color-nexus-border)] text-[var(--color-nexus-text)] hover:bg-slate-600'
                }`}>
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
