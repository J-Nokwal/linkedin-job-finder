"use client";

import { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Application } from "@/lib/client-generated/prisma/client";
import { toggleJobViewed } from "@/app/actions/jobs";
import { ArrowRight, Eye, EyeOff, Briefcase, Building, MapPin } from "lucide-react";

export const columns: ColumnDef<Application>[] = [
  {
    id: "select",
    header: ({ table }) => (
      <Checkbox
        checked={
          table.getIsAllPageRowsSelected() ||
          (table.getIsSomePageRowsSelected() && "indeterminate")
        }
        onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
        aria-label="Select all"
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onCheckedChange={(value) => row.toggleSelected(!!value)}
        aria-label="Select row"
      />
    ),
    enableSorting: false,
    enableHiding: false,
  },
  {
    accessorKey: "companyDetected",
    header: "Company",
    cell: ({ row }) => {
      const company = row.getValue("companyDetected") as string;
      return (
        <div className="flex items-center gap-2">
          <Building className="w-4 h-4 text-muted-foreground" />
          <span className="font-medium">{company || "N/A"}</span>
        </div>
      );
    },
  },
  {
    accessorKey: "roleDetected",
    header: "Role",
    cell: ({ row }) => {
      const role = row.getValue("roleDetected") as string;
      return (
        <div className="flex items-center gap-2">
          <Briefcase className="w-4 h-4 text-muted-foreground" />
          <span>{role || "N/A"}</span>
        </div>
      );
    },
  },
  {
    accessorKey: "locationDetected",
    header: "Location",
    cell: ({ row }) => {
      const location = row.getValue("locationDetected") as string;
      return (
        <div className="flex items-center gap-2">
          <MapPin className="w-4 h-4 text-muted-foreground" />
          <span>{location || "N/A"}</span>
        </div>
      );
    },
  },
  {
    accessorKey: "employmentType",
    header: "Type",
    cell: ({ row }) => {
      const type = row.getValue("employmentType") as string;
      return (
        <Badge variant="secondary" className="text-xs">
          {type?.split("|")[0] || "Unknown"}
        </Badge>
      );
    },
  },
  {
    accessorKey: "seniority",
    header: "Seniority",
    cell: ({ row }) => {
      const seniority = row.getValue("seniority") as string;
      return seniority ? (
        <Badge variant="outline" className="text-xs">
          {seniority}
        </Badge>
      ) : null;
    },
  },
  {
    accessorKey: "isFit",
    header: "Fit",
    cell: ({ row }) => {
      const isFit = row.getValue("isFit") as boolean;
      const fitScore = row.original.fitScore;
      return (
        <div className="flex items-center gap-2">
          <Badge
            variant={isFit ? "default" : "secondary"}
            className="text-xs"
          >
            {isFit ? `Fit (${fitScore}%)` : "Not a fit"}
          </Badge>
        </div>
      );
    },
  },
  {
    accessorKey: "isViewed",
    header: "Status",
    cell: ({ row }) => {
      const isViewed = row.getValue("isViewed") as boolean;
      const id = row.original.id;

      return (
        <div className="flex items-center gap-2">
          <Badge
            variant={isViewed ? "outline" : "default"}
            className="text-xs"
          >
            {isViewed ? "Viewed" : "New"}
          </Badge>
        </div>
      );
    },
  },
  {
    id: "actions",
    cell: ({ row }) => {
      const job = row.original;
      const isViewed = job.isViewed;

      return (
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={async () => {
              await toggleJobViewed(job.id, isViewed);
              // Trigger a re-render or update
              window.location.reload();
            }}
            title={isViewed ? "Mark as unviewed" : "Mark as viewed"}
          >
            {isViewed ? (
              <EyeOff className="w-4 h-4" />
            ) : (
              <Eye className="w-4 h-4" />
            )}
          </Button>
          <Button variant="ghost" size="icon" asChild title="View full details">
            <Link href={`/job/${job.id}`}>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </Button>
        </div>
      );
    },
  },
];
