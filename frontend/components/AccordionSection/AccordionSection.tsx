"use client";

import { ChevronDown } from "lucide-react";
import { useState, type ReactNode } from "react";

type AccordionSectionProps = {
  title: string;
  icon?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
  testId?: string;
  badge?: string;
  contentClassName?: string;
};

function handleAccordionToggle(
  event: React.MouseEvent<HTMLButtonElement>,
  isOpen: boolean,
  setIsOpen: (value: boolean) => void,
) {
  event.preventDefault();
  setIsOpen(!isOpen);
}

export function AccordionSection({
  title,
  icon,
  defaultOpen = false,
  children,
  testId,
  badge,
  contentClassName = "max-h-40 overflow-y-auto pr-1",
}: AccordionSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <section
      className="rounded-xl border border-white/10 bg-black/20"
      data-testid={testId}
    >
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 p-3 text-left"
        onClick={(event) => handleAccordionToggle(event, isOpen, setIsOpen)}
        aria-expanded={isOpen}
      >
        <div className="flex min-w-0 items-center gap-2">
          {icon}
          <span className="truncate text-xs font-bold uppercase tracking-wider text-slate-200">
            {title}
          </span>
          {badge && (
            <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-semibold text-slate-400">
              {badge}
            </span>
          )}
        </div>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-slate-400 transition-transform duration-300 ${
            isOpen ? "rotate-180" : ""
          }`}
        />
      </button>
      {isOpen && (
        <div className={`border-t border-white/5 px-3 pb-3 pt-2 ${contentClassName}`}>
          {children}
        </div>
      )}
    </section>
  );
}
