import * as React from "react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const Button = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & { icon?: React.ReactNode }>(
  ({ className, children, icon, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "group relative inline-flex h-12 items-center justify-center gap-3 overflow-hidden bg-white text-zinc-950 px-8 text-sm font-medium transition-all hover:bg-zinc-200 focus:outline-none focus:ring-2 focus:ring-white/20 active:scale-[0.98]",
          className
        )}
        {...props}
      >
        <span>{children}</span>
        {icon && (
          <span className="transition-transform duration-300 group-hover:translate-x-1">
            {icon}
          </span>
        )}
      </button>
    );
  }
);
Button.displayName = "Button";
