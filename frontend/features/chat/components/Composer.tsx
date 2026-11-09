"use client";

import { ArrowUp, LoaderCircle } from "lucide-react";

export function Composer({
  value,
  onChange,
  onSubmit,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled: boolean;
}) {
  return (
    <div className="border-t border-line bg-white p-3">
      <div className="flex items-end gap-2 rounded-xl border border-line p-2 focus-within:border-accent">
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSubmit();
            }
          }}
          rows={2}
          placeholder="描述告警或问题，Enter 发送，Shift+Enter 换行"
          className="min-h-10 flex-1 resize-none border-0 bg-transparent px-2 py-1.5 text-sm leading-6 outline-none placeholder:text-muted"
          disabled={disabled}
        />
        <button
          type="button"
          onClick={onSubmit}
          disabled={disabled || !value.trim()}
          className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand text-white disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="发送"
        >
          {disabled ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}
