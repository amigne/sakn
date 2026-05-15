import Providers from "./Providers";
import Router from "./Router";
import CookieNotice from "@/components/CookieNotice";

export default function App() {
  return (
    <Providers>
      <Router />
      <CookieNotice />
    </Providers>
  );
}
