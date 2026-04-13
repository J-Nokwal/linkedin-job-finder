"use client";

import { useState, useTransition } from "react";
import { searchJobs } from "@/app/actions/jobs";
import { DataTable } from "@/components/jobs/data-table";
import { columns } from "@/components/jobs/columns";
import { Application } from "@/lib/client-generated/prisma/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search as SearchIcon } from "lucide-react";

export default function SearchClient() {
  const [query, setQuery] = useState("");
  const [jobs, setJobs] = useState<Application[]>([]);
  const [isPending, startTransition] = useTransition();

  const handleSearch = () => {
    startTransition(async () => {
      const results = await searchJobs(query);
      setJobs(results);
    });
  };

  return (
    <div>
      {/* 🔍 Search Bar */}
      <div className="flex gap-2 mb-4">
        <Input
          type="text"
          placeholder="Search title, company, keywords..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          className="flex-1"
        />

        <Button onClick={handleSearch} disabled={isPending}>
          <SearchIcon className="h-4 w-4 mr-2" />
          {isPending ? "Searching..." : "Search"}
        </Button>
      </div>

      {/* ⏳ Loading */}
      {isPending && <p className="text-muted-foreground text-sm">Searching...</p>}

      {/* 📊 Results */}
      {jobs.length > 0 && <DataTable columns={columns} data={jobs} />}

      {!isPending && jobs.length === 0 && query && (
        <p className="text-muted-foreground">No results found</p>
      )}
    </div>
  );
}
