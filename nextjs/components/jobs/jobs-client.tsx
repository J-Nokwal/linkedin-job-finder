"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useTransition } from "react";
import { getJobsByDate } from "@/app/actions/jobs";
import { DataTable } from "@/components/jobs/data-table";
import { columns } from "@/components/jobs/columns";
import { Application } from "@/lib/client-generated/prisma/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";

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
  const [isPending, startTransition] = useTransition();

  const date = searchParams.get("date") || initialDate;

  function setDate(newDate: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("date", newDate);
    router.push(`?${params.toString()}`);
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

      <DataTable columns={columns} data={initialJobs} />
    </div>
  );
}
