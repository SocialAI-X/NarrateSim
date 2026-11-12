/* A small shadcn/ui-style kit on Radix primitives, set to the studio's tokens. */
import * as React from "react";
import * as SelectP from "@radix-ui/react-select";
import * as SliderP from "@radix-ui/react-slider";
import * as SwitchP from "@radix-ui/react-switch";
import * as TooltipP from "@radix-ui/react-tooltip";
import * as DialogP from "@radix-ui/react-dialog";
import * as CollapsibleP from "@radix-ui/react-collapsible";
import { cva, type VariantProps } from "class-variance-authority";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { Check, ChevronDown, X } from "lucide-react";

export const cn = (...c: ClassValue[]) => twMerge(clsx(c));

/* ---------------------------------------------------------------- button --- */
const button = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-full text-[13px] font-medium transition-[background,color,transform,border-color] duration-150 active:scale-[0.97] disabled:pointer-events-none disabled:opacity-40 select-none",
  {
    variants: {
      variant: {
        primary: "bg-ink text-surface hover:bg-soft",
        outline: "border border-control text-ink hover:border-muted hover:bg-hover",
        ghost: "text-soft hover:text-ink hover:bg-hover",
        danger: "border border-control text-negative hover:border-negative",
      },
      size: { sm: "h-7 px-3 text-[12px]", md: "h-[34px] px-4", icon: "h-8 w-8", iconSm: "h-7 w-7" },
    },
    defaultVariants: { variant: "outline", size: "md" },
  },
);
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof button> {}
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, ...p }, ref) => (
  <button ref={ref} className={cn(button({ variant, size }), className)} {...p} />
));
Button.displayName = "Button";

/* ---------------------------------------------------------------- tooltip --- */
export const TooltipProvider = TooltipP.Provider;
export function Tip({ label, children, side = "right" }: { label: React.ReactNode; children: React.ReactNode; side?: "top" | "right" | "bottom" | "left" }) {
  return (
    <TooltipP.Root delayDuration={250}>
      <TooltipP.Trigger asChild>{children}</TooltipP.Trigger>
      <TooltipP.Portal>
        <TooltipP.Content side={side} sideOffset={8} className="z-50 max-w-72 rounded-md bg-raised px-2.5 py-1.5 text-[12px] text-soft shadow-[0_12px_28px_rgba(0,0,0,.35)] data-[state=delayed-open]:animate-in">
          {label}
        </TooltipP.Content>
      </TooltipP.Portal>
    </TooltipP.Root>
  );
}

/* ---------------------------------------------------------------- select ---- */
export function Select<T extends string>({ value, onChange, options, className, ariaLabel }: { value: T; onChange: (v: T) => void; options: { value: T; label: string; hint?: string }[]; className?: string; ariaLabel?: string }) {
  return (
    <SelectP.Root value={value} onValueChange={(v) => onChange(v as T)}>
      <SelectP.Trigger aria-label={ariaLabel} className={cn("flex h-8 w-full items-center justify-between gap-2 rounded-md border border-control bg-surface px-2.5 text-left text-[13px] text-ink hover:border-muted", className)}>
        <SelectP.Value />
        <SelectP.Icon>
          <ChevronDown className="h-3.5 w-3.5 text-muted" />
        </SelectP.Icon>
      </SelectP.Trigger>
      <SelectP.Portal>
        <SelectP.Content position="popper" sideOffset={4} className="z-50 max-h-80 min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-md border border-border bg-raised shadow-[0_12px_28px_rgba(0,0,0,.4)]">
          <SelectP.Viewport className="p-1">
            {options.map((o) => (
              <SelectP.Item key={o.value} value={o.value} className="relative flex cursor-default select-none flex-col rounded px-2 py-1.5 pl-7 text-[13px] text-soft outline-none data-[highlighted]:bg-hover data-[highlighted]:text-ink">
                <SelectP.ItemIndicator className="absolute left-2 top-2">
                  <Check className="h-3.5 w-3.5 text-accent" />
                </SelectP.ItemIndicator>
                <SelectP.ItemText>{o.label}</SelectP.ItemText>
                {o.hint && <span className="text-[11px] text-muted">{o.hint}</span>}
              </SelectP.Item>
            ))}
          </SelectP.Viewport>
        </SelectP.Content>
      </SelectP.Portal>
    </SelectP.Root>
  );
}

/* ---------------------------------------------------------------- slider ---- */
export function Slider({ value, onChange, min, max, step = 1, format, label, disabled }: { value: number; onChange: (v: number) => void; min: number; max: number; step?: number; format?: (v: number) => string; label: string; disabled?: boolean }) {
  return (
    <div className={cn("grid gap-1.5", disabled && "opacity-40")}>
      <div className="flex items-baseline justify-between text-[12px]">
        <span className="text-muted">{label}</span>
        <span className="num text-soft">{format ? format(value) : value}</span>
      </div>
      <SliderP.Root disabled={disabled} aria-label={label} className="relative flex h-4 touch-none select-none items-center" value={[value]} min={min} max={max} step={step} onValueChange={(v) => onChange(v[0])}>
        <SliderP.Track className="relative h-[2px] grow rounded-full bg-control">
          <SliderP.Range className="absolute h-full rounded-full bg-soft" />
        </SliderP.Track>
        <SliderP.Thumb className="block h-3 w-3 rounded-full bg-ink transition-transform hover:scale-125 focus-visible:outline focus-visible:outline-1 focus-visible:outline-accent" />
      </SliderP.Root>
    </div>
  );
}

/* ---------------------------------------------------------------- switch ---- */
export function Switch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <SwitchP.Root aria-label={label} checked={checked} onCheckedChange={onChange} className="relative h-4 w-7 shrink-0 rounded-full bg-control transition-colors data-[state=checked]:bg-accent">
      <SwitchP.Thumb className="block h-3 w-3 translate-x-0.5 rounded-full bg-ink transition-transform data-[state=checked]:translate-x-[14px]" />
    </SwitchP.Root>
  );
}

/* ---------------------------------------------------------------- segmented - */
export function Segmented<T extends string>({ value, onChange, options, size = "md" }: { value: T; onChange: (v: T) => void; options: { value: T; label: React.ReactNode }[]; size?: "sm" | "md" }) {
  return (
    <div role="tablist" className="flex items-center gap-4 border-b border-border">
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={value === o.value}
          data-active={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn("sel-line pb-2 transition-colors", size === "sm" ? "text-[12px]" : "text-[13px]", value === o.value ? "text-ink" : "text-muted hover:text-soft")}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- pill ------ */
const pill = cva("inline-flex h-[18px] items-center gap-1 rounded-full px-2 text-[11px] font-medium whitespace-nowrap", {
  variants: {
    tone: {
      neutral: "bg-raised text-soft",
      positive: "bg-[#1b2828] text-[#5fc39c]",
      negative: "bg-[#2c1a20] text-negative",
      warning: "bg-[#2a2416] text-warning",
      accent: "bg-[#17233a] text-[#7fb0ea]",
    },
  },
  defaultVariants: { tone: "neutral" },
});
export function Pill({ tone, className, ...p }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof pill>) {
  return <span className={cn(pill({ tone }), className)} {...p} />;
}

/* ---------------------------------------------------------------- section --- */
export function Section({ title, aside, children, defaultOpen = true }: { title: string; aside?: React.ReactNode; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <CollapsibleP.Root open={open} onOpenChange={setOpen} className="border-b border-rule">
      <CollapsibleP.Trigger className="flex w-full items-center justify-between px-4 py-3 text-left">
        <span className="text-[13px] font-semibold text-ink">{title}</span>
        <span className="flex items-center gap-2">
          {aside}
          <ChevronDown className={cn("h-3.5 w-3.5 text-muted transition-transform", open && "rotate-180")} />
        </span>
      </CollapsibleP.Trigger>
      <CollapsibleP.Content className="grid gap-3.5 px-4 pb-4">{children}</CollapsibleP.Content>
    </CollapsibleP.Root>
  );
}

export function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="grid gap-1.5">
      <span className="text-[12px] text-muted">{label}</span>
      {children}
      {hint && <span className="text-[11px] leading-snug text-muted">{hint}</span>}
    </label>
  );
}

export function Input(p: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...p} className={cn("h-8 w-full rounded-md border border-control bg-surface px-2.5 text-[13px] text-ink placeholder:text-muted hover:border-muted focus:border-accent focus:outline-none", p.className)} />;
}

/* ---------------------------------------------------------------- dialog ---- */
export function Dialog({ open, onOpenChange, title, description, children }: { open: boolean; onOpenChange: (v: boolean) => void; title: string; description?: string; children: React.ReactNode }) {
  return (
    <DialogP.Root open={open} onOpenChange={onOpenChange}>
      <DialogP.Portal>
        <DialogP.Overlay className="fixed inset-0 z-40 bg-black/60" />
        <DialogP.Content className="fixed left-1/2 top-1/2 z-50 w-[min(560px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border bg-raised p-6 shadow-[0_12px_28px_rgba(0,0,0,.4)]">
          <DialogP.Title className="text-[16px] font-semibold">{title}</DialogP.Title>
          {description && <DialogP.Description className="mt-1 text-[13px] text-muted">{description}</DialogP.Description>}
          <div className="mt-5">{children}</div>
          <DialogP.Close className="absolute right-4 top-4 text-muted hover:text-ink" aria-label="Close">
            <X className="h-4 w-4" />
          </DialogP.Close>
        </DialogP.Content>
      </DialogP.Portal>
    </DialogP.Root>
  );
}

/* ---------------------------------------------------------------- figure ---- */
export function Stat({ label, value, caption, tone }: { label: string; value: React.ReactNode; caption?: React.ReactNode; tone?: "positive" | "negative" | "warning" }) {
  return (
    <div className="min-w-0 px-4 py-3">
      <div className="truncate text-[12px] text-muted">{label}</div>
      <div className={cn("num mt-1 text-[20px] font-medium leading-tight", tone === "negative" && "text-negative", tone === "positive" && "text-positive", tone === "warning" && "text-warning")}>{value}</div>
      {caption && <div className="mt-0.5 truncate text-[11px] text-muted">{caption}</div>}
    </div>
  );
}

export const fmt = {
  signed: (x: number | null | undefined, d = 2) => (x === null || x === undefined || !Number.isFinite(x) ? "—" : `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x).toFixed(d)}`),
  pct: (x: number | null | undefined, d = 0) => (x === null || x === undefined || !Number.isFinite(x) ? "—" : `${(x * 100).toFixed(d)}%`),
  num: (x: number | null | undefined, d = 2) => (x === null || x === undefined || !Number.isFinite(x) ? "—" : x.toFixed(d).replace("-", "−")),
};
