"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, MessageCircle, SendHorizonal } from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/components/providers/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { apiClient, API_BASE_URL } from "@/lib/api-client";
import type { AssistantBootstrap, ChatResponse } from "@/types/kyc";
import type { ApplicationRead } from "@/types/kyc";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export default function AssistantPage() {
  const router = useRouter();
  const { user, token, loading } = useAuth();
  const [bootstrap, setBootstrap] = useState<AssistantBootstrap | null>(null);
  const [referenceId, setReferenceId] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, router, user]);

  useEffect(() => {
    const loadBootstrap = async () => {
      try {
        const [{ data: bootstrapData }, { data: applications }] = await Promise.all([
          apiClient.get<AssistantBootstrap>("/assist/session/bootstrap"),
          apiClient.get<ApplicationRead[]>("/kyc/applications/mine").catch(() => ({ data: [] as ApplicationRead[] })),
        ]);
        setBootstrap(bootstrapData);
        if (applications.length && applications[0].reference_id) {
          setReferenceId(applications[0].reference_id);
        }
      } catch (error) {
        console.error("Failed to bootstrap assistant", error);
      }
    };
    loadBootstrap();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (event?: React.FormEvent) => {
    event?.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || sending) return;
    setMessages((prev) => [...prev, { role: "user", content: trimmed }, { role: "assistant", content: "" }]);
    setInput("");
    setSending(true);
    try {
      await streamMessage(trimmed);
    } catch (error) {
      console.warn("Streaming failed, falling back to JSON", error);
      await fallbackMessage(trimmed);
    } finally {
      setSending(false);
    }
  };

  const streamMessage = async (content: string) => {
    const response = await fetch(`${API_BASE_URL}/assist/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        message: content,
        application_reference_id: referenceId || undefined,
      }),
    });
    if (!response.body) {
      throw new Error("Streaming unsupported");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let assistantReply = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      assistantReply += decoder.decode(value, { stream: true });
      updateLastAssistantMessage(assistantReply);
    }
  };

  const fallbackMessage = async (content: string) => {
    try {
      const { data } = await apiClient.post<ChatResponse>("/assist/chat", {
        message: content,
        application_reference_id: referenceId || undefined,
      });
      updateLastAssistantMessage(data.reply || "...");
    } catch (error) {
      updateLastAssistantMessage("I ran into an issue responding. Please try again in a moment.");
    }
  };

  const updateLastAssistantMessage = (content: string) => {
    setMessages((prev) => {
      const next = [...prev];
      next[next.length - 1] = { role: "assistant", content };
      return next;
    });
  };

  if (!user) {
    return (
      <AppShell title="Assistant" description="Loading session…">
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">Please wait…</CardContent>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell title="Chat with Saral" description="Multilingual assistant with streaming replies and workflow context.">
      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Context</CardTitle>
            <CardDescription>Link your latest application for precise assistance.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="ref">
                Application reference
              </label>
              <Input id="ref" value={referenceId} onChange={(event) => setReferenceId(event.target.value)} placeholder="e.g. 7BBCE9..." />
            </div>
            {bootstrap ? (
              <div className="space-y-2">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Supported languages</p>
                <div className="flex flex-wrap gap-2">
                  {bootstrap.languages.map((lang) => (
                    <Badge key={lang} variant="secondary">
                      {lang.toUpperCase()}
                    </Badge>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">{bootstrap.safety_disclaimer}</p>
              </div>
            ) : null}
            {bootstrap?.suggestion_prompts.length ? (
              <div className="space-y-2">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Quick prompts</p>
                <div className="flex flex-wrap gap-2">
                  {bootstrap.suggestion_prompts.map((prompt) => (
                    <Button key={prompt} variant="outline" size="sm" onClick={() => setInput(prompt)} disabled={sending}>
                      {prompt}
                    </Button>
                  ))}
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle>Assistant</CardTitle>
            <CardDescription>Streaming responses arrive token-by-token.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-1 flex-col gap-4">
            <div className="flex-1 space-y-4 overflow-y-auto rounded-xl border border-border/60 bg-muted/30 p-4">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center gap-2 text-center text-sm text-muted-foreground">
                  <MessageCircle className="h-6 w-6" />
                  Ask about pending documents, risk reasons, or escalation.
                </div>
              ) : (
                messages.map((message, index) => (
                  <div
                    key={`${message.role}-${index}`}
                    className={message.role === "assistant" ? "ml-0 rounded-lg bg-card/80 p-3 shadow-sm" : "ml-auto max-w-[80%] rounded-lg bg-primary p-3 text-primary-foreground"}
                  >
                    {message.content || <Loader2 className="h-4 w-4 animate-spin" />}
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>
            <form onSubmit={handleSend} className="space-y-3">
              <Textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Ask anything in English, हिंदी, বাংলা…"
                rows={3}
                disabled={sending}
              />
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs text-muted-foreground">Press Enter to send, Shift+Enter for a new line.</p>
                <Button type="submit" disabled={sending || !input.trim()}>
                  {sending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Streaming…
                    </>
                  ) : (
                    <>
                      Send <SendHorizonal className="ml-2 h-4 w-4" />
                    </>
                  )}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}

