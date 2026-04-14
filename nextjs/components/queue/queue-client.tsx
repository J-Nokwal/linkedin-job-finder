"use client";

import { useMemo, useState } from "react";
import { ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/jobs/data-table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ApplicationQueue } from "@/lib/client-generated/prisma/client";

interface QueueClientProps {
  initialItems: ApplicationQueue[];
}

export default function QueueClient({ initialItems }: QueueClientProps) {
  const [items, setItems] = useState<ApplicationQueue[]>(initialItems);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const columns = useMemo<ColumnDef<ApplicationQueue, unknown>[]>(
    () => [
      {
        accessorKey: "id",
        header: "ID",
        cell: ({ getValue }) => <span className="bg-gray-200/20 p-1 rounded-xl font-bold text-xs" >{String(getValue() ?? "—")}</span>,
      },
      {
        accessorKey: "postText",
        header: "Post Text",
        cell: ({ getValue }) => {
          const value = String(getValue() || "");
          return <span  className="wrap-break-word">{value.length > 100 ? `${value.slice(0, 100)}...` : value}</span>;
        },
      },
      {
        accessorKey: "source",
        header: "Source",
        cell: ({ getValue }) => <span>{String(getValue() ?? "—")}</span>,
      },
      {
        accessorKey: "postUrl",
        header: "Post URL",
        cell: ({ getValue }) => {
          const url = String(getValue() || "");
          return url ? (
            <a href={url} target="_blank" rel="noreferrer" className="text-primary underline break-all">
              Link
            </a>
          ) : (
            <span className="text-muted-foreground">—</span>
          );
        },
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ getValue }) => {
          const status = String(getValue() || "pending");
          return (
            <Badge variant={status === "pending" ? "secondary" : "outline"} className="text-[11px] uppercase">
              {status}
            </Badge>
          );
        },
      },
      {
        accessorKey: "attemptCount",
        header: "Attempts",
        cell: ({ getValue }) => <span>{String(getValue() ?? "0")}</span>,
      },
      {
        accessorKey: "workerId",
        header: "Worker",
        cell: ({ getValue }) => <span>{String(getValue() ?? "—")}</span>,
      },
      {
        accessorKey: "scrapedAt",
        header: "Scraped At",
        cell: ({ getValue }) => {
          const value = getValue() as string | Date | null;
          const date = value ? new Date(value) : null;
          return <span>{date ? date.toLocaleString() : "—"}</span>;
        },
      },
      {
        id: "actions",
        header: "Actions",
        cell: ({ row }) => {
          const item = row.original;
          const isDeleting = deletingId === item.id;

          return (
            <Button
              variant="destructive"
              size="sm"
              disabled={isDeleting}
              onClick={async () => {
                if (!window.confirm("Delete this queued application?")) {
                  return;
                }

                setDeletingId(item.id);
                setErrorMessage(null);

                try {
                  const response = await fetch("/api/jobs/queue/delete", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ queueId: item.id }),
                  });

                  const result = await response.json();

                  if (!response.ok || !result.success) {
                    throw new Error(result.error || "Failed to delete queue item");
                  }

                  setItems((current) => current.filter((queueItem) => queueItem.id !== item.id));
                } catch (error) {
                  setErrorMessage(
                    error instanceof Error ? error.message : "Unable to delete queue item"
                  );
                } finally {
                  setDeletingId(null);
                }
              }}
            >
              Delete
            </Button>
          );
        },
      },
    ],
    [deletingId]
  );

  return (
    <div className="space-y-4">
      {errorMessage ? (
        <div className="bg-destructive/10 p-3 border border-destructive/50 rounded-md text-destructive text-sm">
          {errorMessage}
        </div>
      ) : null}
      <DataTable columns={columns} data={items} />
    </div>
  );
}
