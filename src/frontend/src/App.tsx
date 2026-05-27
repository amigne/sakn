import CookieNotice from "@/components/CookieNotice";
import Providers from "./Providers";
import Router from "./Router";

export default function App() {
  return (
    <Providers>
      <Router />
      <CookieNotice />
    </Providers>
  );
}
