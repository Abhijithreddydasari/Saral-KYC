import Link from "next/link";

import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function HomePage() {
  return (
    <AppShell title="KYC superpowers" description="Streamlined onboarding for admins, analysts, and customers.">
      <section className="flex flex-col gap-6">
        <div>
          <Badge className="mb-3" variant="secondary">
            Saral-KYC prototype
          </Badge>
          <h2 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">Launch into the unified workspace</h2>
          <p className="mt-3 max-w-3xl text-base text-muted-foreground sm:text-lg">
            Rerun the entire onboarding loop from a single console: create applications, upload documents, check risk posture, and collaborate with the multilingual
            assistant—all backed by FastAPI.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link href="/login" className="inline-block">
              <Button size="lg">Log in / Sign up</Button>
            </Link>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>API-ready</CardTitle>
              <CardDescription>Fetch application summaries, preview documents, and chat bootstrap metadata.</CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Configure <code>NEXT_PUBLIC_API_BASE_URL</code> then use <code>lib/api-client.ts</code> for authenticated requests. Server components stay data-fetching
              friendly while client components handle uploads and progress streaming.
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Design system</CardTitle>
              <CardDescription>Tailwind + shadcn/ui primitives for consistent UX.</CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Buttons, cards, tables, progress bars, and badges are ready. Plug them into dashboard panels, document previews, and the conversational assistant drawer
              without redoing styles.
            </CardContent>
          </Card>
        </div>
      </section>
    </AppShell>
  );
}

