import Link from "next/link";
import { FileQuestion, Home, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFoundPage() {
  return (
    <div className="min-h-screen bg-[var(--background)] flex items-center justify-center p-6">
      <div className="max-w-md w-full p-8 rounded-3xl border border-[var(--border)] bg-[var(--card)] shadow-2xl text-center space-y-6">
        <div className="mx-auto h-16 w-16 rounded-2xl bg-sky-500/10 text-sky-500 flex items-center justify-center">
          <FileQuestion className="h-8 w-8" />
        </div>

        <div className="space-y-2">
          <span className="text-xs font-bold uppercase tracking-wider text-sky-500">
            404 Error
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--foreground)]">
            Page Not Found
          </h1>
          <p className="text-sm text-[var(--muted-foreground)]">
            The page or resource you requested could not be located on the Smart Classroom platform.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-center gap-3 justify-center pt-2">
          <Link href="/" className="w-full sm:w-auto">
            <Button className="w-full gap-2 rounded-xl" aria-label="Go to home landing page">
              <Home className="h-4 w-4" />
              Return Home
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}

