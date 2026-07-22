import { Link } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { XCircle, ArrowLeft } from "lucide-react";

export default function PaymentCancel() {
  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="w-full max-w-md">
        <Card
          data-testid="payment-cancel-card"
          className="bg-card border border-border rounded-sm p-8"
        >
          <div className="flex items-start gap-3">
            <div className="border border-border p-2 rounded-sm">
              <XCircle className="h-5 w-5 text-muted-foreground" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-1">
                Canceled
              </p>
              <h1 className="font-display text-3xl tracking-tight">No charge made.</h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Your card wasn&apos;t billed. You can upgrade any time from Settings.
              </p>
            </div>
          </div>
          <Link
            to="/settings"
            data-testid="payment-cancel-return"
            className="mt-8 inline-flex items-center gap-2 h-11 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-colors duration-200 px-5 text-sm font-medium"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Settings
          </Link>
        </Card>
      </div>
    </div>
  );
}
