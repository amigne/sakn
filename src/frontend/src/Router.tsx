import { Routes, Route, Navigate } from "react-router-dom";

export default function Router() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/ping" replace />} />
      <Route path="/ping" element={<div>Ping Page (Slice 2)</div>} />
      <Route path="/traceroute" element={<div>Traceroute Page (Slice 2)</div>} />
      <Route path="/dns" element={<div>DNS Lookup Page (Slice 2)</div>} />
      <Route path="/ssl" element={<div>SSL Viewer Page (Slice 2)</div>} />
      <Route path="*" element={<div>Not Found</div>} />
    </Routes>
  );
}
