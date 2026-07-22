import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Mail, Send } from "lucide-react";

export default function DigestCard() {
  const [enabled, setEnabled] = useState(true);
  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const p = await api.getPreferences();
        setEnabled(!!p.weekly_digest_enabled);
      } catch {
        // Silent — non-critical.
      }
    })();
  }, []);

  const toggle = async (next) => {
    setBusy(true);
    setEnabled(next); // optimistic
    try {
      await api.updatePreferences(next);
      toast.success(next ? "Weekly digest turned on" : "Weekly digest turned off");
    } catch (err) {
      setEnabled(!next); // revert
      toast.error(err?.data?.detail || "Failed to update preference");
    } finally {
      setBusy(false);
    }
  };

  const sendTest = async () => {
    setSending(true);
    try {
      await api.digestSendTest();
      toast.success("Digest sent — check your inbox in a minute.");
    } catch (err) {
      toast.error(err?.data?.detail || "Failed to send digest");
    } finally {
      setSending(false);
    }
  };

  return (
    <Card
      data-testid="settings-digest-card"
      className="md:col-span-4 bg-card border border-border rounded-sm p-8"
    >
      <div className="flex items-start gap-4">
        <div className="border border-border p-2 rounded-sm">
          <Mail className="h-4 w-4" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground mb-1">
            Weekly digest
          </p>
          <h2 className="font-display text-lg tracking-tight">
            Progress Digest — every Monday
          </h2>
          <p className="text-xs text-muted-foreground mt-1 max-w-lg">
            Portfolio average, top movers this week, and shipped next-steps —
            delivered by email. You can turn it off any time.
          </p>

          <div className="mt-6 flex items-center gap-3">
            <Switch
              data-testid="digest-toggle-switch"
              checked={enabled}
              disabled={busy}
              onCheckedChange={toggle}
            />
            <Label
              className="text-sm cursor-pointer"
              onClick={() => !busy && toggle(!enabled)}
            >
              {enabled ? "On — sends every Monday 10:00am ET" : "Off"}
            </Label>
          </div>

          <div className="mt-8 pt-6 border-t border-border flex items-center gap-3 flex-wrap">
            <Button
              onClick={sendTest}
              disabled={sending}
              variant="outline"
              data-testid="digest-send-test-button"
              className="h-10 rounded-sm bg-background border border-border hover:bg-white/5 transition-colors duration-200 px-4"
            >
              <Send className="h-3.5 w-3.5 mr-2" />
              {sending ? "Sending…" : "Send me a preview now"}
            </Button>
            <span className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
              Uses your account email
            </span>
          </div>
        </div>
      </div>
    </Card>
  );
}
