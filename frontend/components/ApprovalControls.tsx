"use client";

type ApprovalControlsProps = {
  onApprove: () => void;
  onReject?: () => void;
  approveLabel?: string;
  rejectLabel?: string;
  extraActions?: Array<{ label: string; onClick: () => void }>;
  disabled?: boolean;
};

export function ApprovalControls({
  onApprove,
  onReject,
  approveLabel = "Approve",
  rejectLabel = "Reject",
  extraActions = [],
  disabled = false,
}: ApprovalControlsProps) {
  return (
    <div className="glass-card flex flex-wrap items-center gap-3" data-testid="approval-controls">
      <p className="mr-auto text-sm text-slate-400">You are the creative director. Agents do the editing.</p>
      <button type="button" className="glass-button bg-neonGreen/20" disabled={disabled} onClick={onApprove}>
        {approveLabel}
      </button>
      {onReject && (
        <button type="button" className="glass-button bg-pink-500/20" disabled={disabled} onClick={onReject}>
          {rejectLabel}
        </button>
      )}
      {extraActions.map((action) => (
        <button key={action.label} type="button" className="glass-button" disabled={disabled} onClick={action.onClick}>
          {action.label}
        </button>
      ))}
    </div>
  );
}
