import { Navigate } from "react-router-dom";
import { useAvailableTools, TOOL_ROUTES } from "@/hooks/useAvailableTools";
import { Spinner } from "@/components/ui";

interface Props {
  toolName: string;
  children: React.ReactNode;
}

export default function ToolGuard({ toolName, children }: Props) {
  const { tools, checked } = useAvailableTools();

  if (!checked) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!tools.includes(toolName)) {
    const first = tools[0];
    return <Navigate to={first ? TOOL_ROUTES[first] ?? "/ping" : "/no-tools"} replace />;
  }

  return <>{children}</>;
}
