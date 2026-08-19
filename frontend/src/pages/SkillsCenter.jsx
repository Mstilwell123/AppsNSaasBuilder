import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { Card } from "@/components/ui/card";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Sparkles } from "lucide-react";

const CATEGORY_ORDER = ["Discovery", "Product", "Architecture", "Build", "Quality", "Launch", "Business"];

export default function SkillsCenter() {
  const [skills, setSkills] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const data = await api.listSkills();
        setSkills(data.skills || []);
      } catch (err) {
        toast.error("Failed to load skills");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const grouped = skills.reduce((acc, s) => {
    const cat = s.category || "Other";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(s);
    return acc;
  }, {});

  return (
    <AppShell active="skills">
      <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">Hermes Skills</p>
      <h1 className="font-display text-4xl sm:text-5xl tracking-tight mb-2">Skills Library</h1>
      <p className="text-sm text-muted-foreground max-w-lg mb-10">
        AppsNSaas-specific Hermes skills for every stage — from idea to launch to business. Use these with Hermes Agent to build, audit, and ship.
      </p>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading skills…</p>
      ) : (
        <div className="space-y-8">
          {CATEGORY_ORDER.map((cat) => (
            grouped[cat] && (
              <div key={cat}>
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-4">{cat}</p>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {grouped[cat].map((skill) => (
                    <Card key={skill.key} data-testid={`skill-${skill.key}`} className="bg-card border border-border rounded-sm p-4">
                      <div className="flex items-start gap-3">
                        <Sparkles className="h-4 w-4 text-muted-foreground mt-0.5" />
                        <div>
                          <h3 className="text-sm font-medium">{skill.name}</h3>
                          <p className="text-xs text-muted-foreground mt-1">{skill.description}</p>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>
            )
          ))}
        </div>
      )}
    </AppShell>
  );
}
