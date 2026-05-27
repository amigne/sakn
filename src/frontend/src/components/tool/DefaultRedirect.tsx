import { Navigate } from "react-router-dom";
import { Spinner } from "@/components/ui";
import { TOOL_ROUTES, useAvailableTools } from "@/hooks/useAvailableTools";

export default function DefaultRedirect() {
  const { tools, checked } = useAvailableTools();

  if (!checked) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }

  const first = tools[0];
  if (first && TOOL_ROUTES[first]) {
    return <Navigate to={TOOL_ROUTES[first]} replace />;
  }

  return <Navigate to="/no-tools" replace />;
}
