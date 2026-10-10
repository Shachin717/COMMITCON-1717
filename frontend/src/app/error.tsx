"use client";

import * as React from "react";
import Link from "next/link";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function ErrorBoundaryPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  React.useEffect(() => {
    console.error("App boundary error caught:", error);
  }, [error]);

  return (
    <div
      role="alert"
      className="min-h-screen bg-[var(--background)] flex items-center justify-center p-6"
    >
      <div className="max-w-md w-full p-8 rounded-3xl border border-[var(--border)] bg-[var(--card)] shadow-2xl text-center space-y-6">
        <div className="mx-auto h-16 w-16 rounded-2xl bg-rose-500/10 text-rose-500 flex items-center justify-center">
          <AlertTriangle className="h-8 w-8" />
        </div>

        <div className="space-y-2">
          <h1 className="text-2xl font-bold tracking-tight text-[var(--foreground)]">
            Something went wrong
          </h1>
          <p className="text-sm text-[var(--muted-foreground)]">
            {error?.message || "An unexpected error occurred while processing this page."}
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-center gap-3 justify-center pt-2">
          <Button
            onClick={() => reset()}
            className="w-full sm:w-auto gap-2 rounded-xl"
            aria-label="Try reloading page"
          >
            <RefreshCw className="h-4 w-4" />
            Try Again
          </Button>
          <Link href="/" className="w-full sm:w-auto">
            <Button
              variant="outline"
              className="w-full gap-2 rounded-xl"
              aria-label="Navigate to home page"
            >
              <Home className="h-4 w-4" />
              Return Home
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}

