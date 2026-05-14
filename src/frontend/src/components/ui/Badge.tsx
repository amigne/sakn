interface BadgeProps {
  variant?: "success" | "warning" | "error" | "info" | "neutral";
  children: React.ReactNode;
  className?: string;
}

const variantClasses: Record<string, string> = {
  success: "bg-success-50 text-success-700 dark:bg-success-700/20 dark:text-success-500",
  warning: "bg-warning-50 text-warning-700 dark:bg-warning-700/20 dark:text-warning-500",
  error: "bg-error-50 text-error-700 dark:bg-error-700/20 dark:text-error-500",
  info: "bg-info-50 text-info-700 dark:bg-info-700/20 dark:text-info-500",
  neutral: "bg-gray-100 text-gray-700 dark:bg-gray-700/30 dark:text-gray-400",
};

export default function Badge({ variant = "neutral", children, className = "" }: BadgeProps) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  );
}
