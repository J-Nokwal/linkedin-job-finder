"use client";

import { useCallback, useMemo, useState } from "react";
import { ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/jobs/data-table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { ApplicationQueue } from "@/lib/client-generated/prisma/client";

interface QueueClientProps {
  initialItems: ApplicationQueue[];
}

export default function QueueClient({ initialItems }: QueueClientProps) {
  const [items, setItems] = useState<ApplicationQueue[]>(initialItems);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [selectedRows, setSelectedRows] = useState<ApplicationQueue[]>([]);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSelectedRowsChange = useCallback(
    (rows: ApplicationQueue[]) => setSelectedRows(rows),
    []
  );

  async function deleteSingle(id: string) {
    setDeletingId(id);
    setErrorMessage(null);
    try {
      const res = await fetch("/api/jobs/queue/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ queueId: id }),
      });
      const result = await res.json();
      if (!res.ok || !result.success) throw new Error(result.error || "Failed to delete");
      setItems((prev) => prev.filter((q) => q.id !== id));
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Unable to delete queue item");
    } finally {
      setDeletingId(null);
    }
  }

  async function deleteSelected() {
    if (!selectedRows.length) return;
    if (!window.confirm(`Delete ${selectedRows.length} selected item${selectedRows.length === 1 ? "" : "s"}?`)) return;

    setIsBulkDeleting(true);
    setErrorMessage(null);
    const ids = selectedRows.map((r) => r.id);
    try {
      const res = await fetch("/api/jobs/queue/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ queueIds: ids }),
      });
      const result = await res.json();
      if (!res.ok || !result.success) throw new Error(result.error || "Failed to delete");
      setItems((prev) => prev.filter((q) => !ids.includes(q.id)));
      setSelectedRows([]);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Unable to delete selected items");
    } finally {
      setIsBulkDeleting(false);
    }
  }

  const columns = useMemo<ColumnDef<ApplicationQueue, unknown>[]>(
    () => [
      {
        id: "select",
        header: ({ table }) => (
          <Checkbox
            checked={
              table.getIsAllPageRowsSelected()
                ? true
                : table.getIsSomePageRowsSelected()
                ? "indeterminate"
                : false
            }
            onCheckedChange={(v) => table.toggleAllPageRowsSelected(!!v)}
            aria-label="Select all"
          />
        ),
        cell: ({ row }) => (
          <Checkbox
            checked={row.getIsSelected()}
            onCheckedChange={(v) => row.toggleSelected(!!v)}
            aria-label="Select row"
            onClick={(e) => e.stopPropagation()}
          />
        ),
        enableSorting: false,
      },
      {
        accessorKey: "id",
        header: "ID",
        cell: ({ getValue }) => (
          <span className="bg-gray-200/20 p-1 rounded-xl font-bold text-xs">
            {String(getValue() ?? "—")}
          </span>
        ),
      },
      {
        accessorKey: "postText",
        header: "Post Text",
        cell: ({ getValue }) => {
          const value = String(getValue() || "");
          return (
            <span className="wrap-break-word">
              {value.length > 100 ? `${value.slice(0, 100)}...` : value}
            </span>
          );
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
              disabled={isDeleting || isBulkDeleting}
              onClick={async () => {
                if (!window.confirm("Delete this queued item?")) return;
                await deleteSingle(item.id);
              }}
            >
              {isDeleting ? "Deleting…" : "Delete"}
            </Button>
          );
        },
      },
    ],
    [deletingId, isBulkDeleting] // eslint-disable-line react-hooks/exhaustive-deps
  );

  return (
    <div className="space-y-4">
      {errorMessage ? (
        <div className="bg-destructive/10 p-3 border border-destructive/50 rounded-md text-destructive text-sm">
          {errorMessage}
        </div>
      ) : null}

      {selectedRows.length > 0 && (
        <div className="flex items-center gap-3 bg-muted/50 px-4 py-2 border rounded-md">
          <span className="text-sm">{selectedRows.length} item{selectedRows.length === 1 ? "" : "s"} selected</span>
          <Button
            variant="destructive"
            size="sm"
            disabled={isBulkDeleting}
            onClick={deleteSelected}
          >
            {isBulkDeleting ? "Deleting…" : `Delete Selected (${selectedRows.length})`}
          </Button>
        </div>
      )}

      <DataTable
        columns={columns}
        data={items}
        onSelectedRowsChange={handleSelectedRowsChange}
        getRowId={(row) => row.id}
      />
    </div>
  );
}
