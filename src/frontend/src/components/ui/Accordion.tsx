import * as RadixAccordion from "@radix-ui/react-accordion";
import type { ReactNode } from "react";

interface AccordionItem {
  value: string;
  trigger: ReactNode;
  content: ReactNode;
}

interface AccordionProps {
  items: AccordionItem[];
  type?: "single" | "multiple";
  defaultValue?: string;
  className?: string;
}

export default function Accordion({ items, type = "single", defaultValue, className = "" }: AccordionProps) {
  if (type === "single") {
    return (
      <RadixAccordion.Root type="single" defaultValue={defaultValue} collapsible className={`w-full ${className}`}>
        {items.map((item) => (
          <RadixAccordion.Item key={item.value} value={item.value} className="border-b border-[var(--color-border)]">
            <RadixAccordion.Header>
              <RadixAccordion.Trigger className="focus-ring flex w-full items-center justify-between px-3 py-2 text-sm font-medium text-[var(--color-text)] hover:bg-[var(--color-surface-alt)]">
                {item.trigger}
                <svg
                  className="h-4 w-4 text-[var(--color-text-secondary)] transition-transform data-[state=open]:rotate-180"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </RadixAccordion.Trigger>
            </RadixAccordion.Header>
            <RadixAccordion.Content className="overflow-hidden data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down">
              <div className="px-3 pb-3 text-sm text-[var(--color-text)]">{item.content}</div>
            </RadixAccordion.Content>
          </RadixAccordion.Item>
        ))}
      </RadixAccordion.Root>
    );
  }

  return (
    <RadixAccordion.Root
      type="multiple"
      defaultValue={defaultValue ? [defaultValue] : undefined}
      className={`w-full ${className}`}
    >
      {items.map((item) => (
        <RadixAccordion.Item key={item.value} value={item.value} className="border-b border-[var(--color-border)]">
          <RadixAccordion.Header>
            <RadixAccordion.Trigger className="focus-ring flex w-full items-center justify-between px-3 py-2 text-sm font-medium text-[var(--color-text)] hover:bg-[var(--color-surface-alt)]">
              {item.trigger}
              <svg
                className="h-4 w-4 text-[var(--color-text-secondary)] transition-transform data-[state=open]:rotate-180"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </RadixAccordion.Trigger>
          </RadixAccordion.Header>
          <RadixAccordion.Content className="overflow-hidden data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down">
            <div className="px-3 pb-3 text-sm text-[var(--color-text)]">{item.content}</div>
          </RadixAccordion.Content>
        </RadixAccordion.Item>
      ))}
    </RadixAccordion.Root>
  );
}
