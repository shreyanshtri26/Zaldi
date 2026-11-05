import { Card, PageHeader } from "../components/ui";

/** Sections that belong to later phases. Their working versions still live in the current admin app. */
export default function ComingSoon({ title, phase }: { title: string; phase: string }) {
  return (
    <>
      <PageHeader eyebrow="Planned" title={title} />
      <Card className="p-6">
        <p>This screen is planned for {phase}.</p>
        <p className="mt-2 text-ink2">Until then, use the current admin at <code className="text-primary">/admin</code> on the main app (port 5173).</p>
      </Card>
    </>
  );
}
