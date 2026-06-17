"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState, useTransition } from "react";
import { DataTable } from "@/components/jobs/data-table";
import { columns } from "@/components/jobs/columns";
import { Application } from "@/lib/client-generated/prisma/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

function shiftDate(dateStr: string, diff: number) {
  const date = new Date(dateStr);
  date.setDate(date.getDate() + diff);
  return date.toISOString().split("T")[0];
}

function getTodayUTC() {
  const now = new Date();
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()))
    .toISOString()
    .split("T")[0];
}

export default function JobsClient({
  initialJobs,
  initialDate,
}: {
  initialJobs: Application[];
  initialDate: string;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isPending] = useTransition();

  const date = searchParams.get("date") || initialDate;
  const [selectedJobs, setSelectedJobs] = useState<Application[]>([]);
  const [isDeleting, setIsDeleting] = useState(false);
  const [tableKey, setTableKey] = useState(0);

  function setDate(newDate: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("date", newDate);
    router.push(`?${params.toString()}`);
  }

  async function handleDeleteSelected() {
    if (!selectedJobs.length) {
      return;
    }

    if (!window.confirm(`Delete ${selectedJobs.length} selected job${selectedJobs.length === 1 ? "" : "s"}?`)) {
      return;
    }

    setIsDeleting(true);

    try {
      const response = await fetch("/api/jobs/delete", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ids: selectedJobs.map((job) => job.id) }),
      });

      const result = await response.json();

      if (!response.ok || !result.success) {
        throw new Error(result.error || "Failed to delete selected jobs");
      }

      setSelectedJobs([]);
      setTableKey((k) => k + 1);
      router.refresh();
    } catch (error) {
      console.error(error);
      window.alert(error instanceof Error ? error.message : "Unable to delete selected jobs.");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <div className="mt-4">
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <label className="font-medium text-sm">Filter by date:</label>

        <Button
          variant="outline"
          size="sm"
          onClick={() => setDate(shiftDate(date, -1))}
        >
          ← Prev
        </Button>

        <Input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="w-40"
        />

        <Button
          variant="outline"
          size="sm"
          onClick={() => setDate(shiftDate(date, 1))}
        >
          Next →
        </Button>

        <Button
          variant="default"
          size="sm"
          onClick={() => setDate(getTodayUTC())}
        >
          Today
        </Button>

        {isPending && <span className="text-muted-foreground text-sm">Loading...</span>}
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <Button
          variant="destructive"
          size="sm"
          onClick={handleDeleteSelected}
          disabled={selectedJobs.length === 0 || isDeleting}
        >
          {isDeleting ? "Deleting..." : `Delete selected (${selectedJobs.length})`}
        </Button>
      </div>

      <DataTable
        key={tableKey}
        columns={columns}
        data={initialJobs}
        onSelectedRowsChange={setSelectedJobs}
        getRowId={(row) => row.id}
      />
    </div>
  );
}
