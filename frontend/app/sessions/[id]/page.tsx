import { Workbench } from "@/features/chat/Workbench";

export default async function SessionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <Workbench sessionId={id} />;
}
