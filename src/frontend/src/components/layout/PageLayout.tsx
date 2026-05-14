import type { ReactNode } from "react";
import TopBar from "./TopBar";
import Sidebar from "./Sidebar";

interface PageLayoutProps {
  children: ReactNode;
}

export default function PageLayout({ children }: PageLayoutProps) {
  return (
    <div className="flex h-screen flex-col bg-gray-100 dark:bg-gray-950 text-gray-900 dark:text-gray-100">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-auto p-4">
          {children}
        </main>
      </div>
      <footer className="border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-4 py-1 text-center text-xs text-gray-500 dark:text-gray-400">
        SAKN v0.0.1 — Swiss Army Knife for Network Engineers
      </footer>
    </div>
  );
}
