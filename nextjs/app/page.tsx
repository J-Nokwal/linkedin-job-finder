import JobsClient from "@/components/jobs/jobs-client";
import { getJobsByDate } from "./actions/jobs";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Suspense } from "react";
import AutoRefresh from "@/components/common/clientRefresh";
export const dynamic = "force-dynamic";

function getTodayUTC() {
  const now = new Date();
  const utc = new Date(
    Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()),
  );
  return utc.toISOString().split("T")[0];
}

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const { autoRefresh, date } = await searchParams;
  const today = getTodayUTC();
  const activeDate = (date as string) || today;
  const jobs = await getJobsByDate(activeDate);

  return (
    <>
      {autoRefresh === "true" && <Suspense>
        <AutoRefresh />
      </Suspense>}
      <div className="p-6">
        <div className="flex justify-between items-center">
          <h1 className="font-bold text-2xl">Applied Jobs</h1>
          <div className="flex gap-2">
            <div className="flex items-center gap-2">
              <form method="GET" className="flex items-center gap-6">
                <FieldGroup className="mx-auto w-56">
                  <Field orientation="horizontal">
                    <Checkbox
                      id="terms-checkbox-basic"
                      type="submit"
                      name="autoRefresh"
                      value="true"
                      defaultChecked={autoRefresh === "true"}
                    />
                    <FieldLabel htmlFor="terms-checkbox-basic">
                      Auto Refresh (5s)
                    </FieldLabel>
                  </Field>
                </FieldGroup>
              </form>
            </div>
            <Button variant={"link"}>
              <Link href="/search-job" className="underline">
                Search
              </Link>
            </Button>
          </div>
        </div>

        <JobsClient initialJobs={jobs} initialDate={activeDate} />
      </div>
    </>
  );
}
