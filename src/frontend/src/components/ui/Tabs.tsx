import * as RadixTabs from "@radix-ui/react-tabs";

interface Tab {
  value: string;
  label: string;
}

interface TabsProps {
  tabs: Tab[];
  value: string;
  onChange: (value: string) => void;
  children: React.ReactNode;
  className?: string;
}

export default function Tabs({ tabs, value, onChange, children, className = "" }: TabsProps) {
  return (
    <RadixTabs.Root value={value} onValueChange={onChange} className={className}>
      <RadixTabs.List className="flex border-b border-[var(--color-border)]" aria-label="Tabs">
        {tabs.map((tab) => (
          <RadixTabs.Trigger
            key={tab.value}
            value={tab.value}
            className={`focus-ring px-4 py-2.5 text-sm font-medium border-b-2 transition-colors
              ${
                value === tab.value
                  ? "border-primary-600 text-primary-600"
                  : "border-transparent text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
              }`}
          >
            {tab.label}
          </RadixTabs.Trigger>
        ))}
      </RadixTabs.List>
      {children}
    </RadixTabs.Root>
  );
}
