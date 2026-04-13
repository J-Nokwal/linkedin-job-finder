import SearchClient from "@/components/jobs/search-client";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function Page() {
  return (
    <div className="gap-2 p-6">
      <Button variant={"default"}>
        <Link href="/" className="underline">
          Back
        </Link>
      </Button>
      <h1 className="mb-4 font-bold text-2xl">Search Jobs</h1>
      <SearchClient />
    </div>
  );
}
