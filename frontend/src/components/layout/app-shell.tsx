"use client";

import { ReactNode } from "react";
import { ArrowLeft, LogOut, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface AppShellProps {
  title?: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  hideBackButton?: boolean;
}

export function AppShell({ title, description, actions, children, hideBackButton = false }: AppShellProps) {
  const router = useRouter();
  const { user, logout } = useAuth();

  const initials = user?.full_name
    ? user.full_name
        .split(" ")
        .map((chunk) => chunk.charAt(0))
        .slice(0, 2)
        .join("")
        .toUpperCase()
    : "??";

  return (
    <div className="min-h-screen bg-gradient-to-b from-background via-background to-muted/40 text-foreground">
      <header className="sticky top-0 z-20 border-b border-border/60 bg-background/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-2">
            {!hideBackButton && (
              <Button variant="ghost" size="icon" className="h-9 w-9 rounded-full border border-border/60" onClick={() => router.back()}>
                <ArrowLeft className="h-4 w-4" />
              </Button>
            )}
            <span className="text-sm text-muted-foreground">Saral-KYC</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-sm font-medium">{user?.full_name ?? "Guest"}</p>
              <p className="text-xs text-muted-foreground">{user?.is_admin ? "Admin" : "User"}</p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-full border border-border/60 bg-card text-sm font-semibold">
              {user ? initials : <UserRound className="h-4 w-4" />}
            </div>
            {user ? (
              <Button variant="ghost" size="icon" className="h-9 w-9 rounded-full" onClick={logout}>
                <LogOut className="h-4 w-4" />
              </Button>
            ) : null}
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl space-y-8 px-4 py-8">
        {(title || description || actions) && (
          <div className="flex flex-col gap-3 border-b border-border/40 pb-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              {title ? <h1 className="text-2xl font-semibold tracking-tight">{title}</h1> : null}
              {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
            </div>
            {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
          </div>
        )}

        <div className={cn("space-y-6", !title && !description ? "pt-4" : "")}>{children}</div>
      </main>
    </div>
  );
}

