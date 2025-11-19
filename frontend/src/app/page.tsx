import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-muted/30">
      <section className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-16">
        <div>
          <Badge className="mb-3" variant="secondary">
            Saral-KYC prototype
          </Badge>
          <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">KYC superpowers for ops + customers</h1>
          <p className="mt-4 max-w-3xl text-base text-muted-foreground sm:text-lg">
            This frontend consumes the FastAPI hooks you just added: document telemetry, risk explanations, workflow nudges, and the multilingual assistant.
            Build the upload wizard and staff dashboard on top of this scaffold.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/ops" className="inline-block">
              <Button size="lg">Open operator console</Button>
            </Link>
            <Link href="/wizard" className="inline-block">
              <Button size="lg" variant="outline">
                Preview applicant flow
              </Button>
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
    </main>
  );
}

