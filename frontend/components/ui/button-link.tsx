import Link from "next/link";
import { type ComponentProps } from "react";
import { buttonClasses, type ButtonSize, type ButtonVariant } from "./button";

/**
 * A navigation link that looks like a button.
 *
 * Replaces the hand-copied class strings that used to style links as buttons
 * across pages: a link stays a link for assistive technology and for "open in a
 * new tab", and only borrows the look.
 */
export function ButtonLink({
  variant = "secondary",
  size = "sm",
  className,
  ...props
}: ComponentProps<typeof Link> & { variant?: ButtonVariant; size?: ButtonSize }) {
  return <Link className={buttonClasses(variant, size, className)} {...props} />;
}
