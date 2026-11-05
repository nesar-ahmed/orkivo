import { type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils/cn";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "danger-solid";
export type ButtonSize = "xs" | "sm" | "md" | "icon" | "icon-sm";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const baseStyles =
  "inline-flex shrink-0 items-center justify-center gap-1.5 rounded-md font-medium whitespace-nowrap " +
  "transition-[color,background-color,border-color,box-shadow] duration-150 select-none " +
  "disabled:pointer-events-none disabled:opacity-50 [&_svg]:shrink-0";

export const buttonVariants: Record<ButtonVariant, string> = {
  primary: "bg-primary text-primary-foreground shadow-xs hover:bg-primary-hover",
  secondary:
    "border border-border bg-card text-card-foreground shadow-xs hover:border-border-strong hover:bg-muted",
  ghost: "text-muted-foreground hover:bg-muted hover:text-foreground",
  danger: "text-danger hover:bg-danger/10",
  "danger-solid": "bg-danger text-danger-foreground shadow-xs hover:opacity-90",
};

export const buttonSizes: Record<ButtonSize, string> = {
  xs: "h-7 px-2 text-xs [&_svg]:size-3.5",
  sm: "h-8 px-3 text-sm [&_svg]:size-4",
  md: "h-9 px-4 text-sm [&_svg]:size-4",
  icon: "size-9 [&_svg]:size-4",
  "icon-sm": "size-7 [&_svg]:size-4",
};

/** Class names for anything that should look like a button (links, triggers). */
export function buttonClasses(
  variant: ButtonVariant = "primary",
  size: ButtonSize = "md",
  className?: string,
): string {
  return cn(baseStyles, buttonVariants[variant], buttonSizes[size], className);
}

export function Button({
  variant = "primary",
  size = "md",
  className,
  type = "button",
  ...props
}: ButtonProps) {
  return <button type={type} className={buttonClasses(variant, size, className)} {...props} />;
}
