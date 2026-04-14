import Link from "next/link";
import { Button } from "@/components/ui/button";
import QueueClient from "@/components/queue/queue-client";
import { getPendingQueueItems, countPendingQueueItems } from "@/app/actions/queue";

export const dynamic = "force-dynamic";

export default async function Page() {
  const queueItems = await getPendingQueueItems();
  const total = await countPendingQueueItems();

  return (
    <div className="p-6">
      <div className="flex md:flex-row flex-col md:justify-between md:items-center gap-4 mb-6">
        <div>
          <h1 className="font-bold text-2xl">Application Queue</h1>
          <p className="mt-1 text-muted-foreground text-sm">
            Showing uncompleted queue items only. Page size is 100 items per page.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" asChild>
            <Link href="/">Back</Link>
          </Button>
          <Button variant="default" asChild>
            <Link href="/search-job">Search</Link>
          </Button>
        </div>
      </div>

      <div className="mb-4 text-muted-foreground text-sm">
        {total === 0 ? "No uncompleted queue items found." : `${total} uncompleted queue item${total === 1 ? "" : "s"} total.`}
      </div>

      <QueueClient initialItems={queueItems} />
    </div>
  );
}
