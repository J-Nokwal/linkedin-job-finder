"use client";

import { markJobAsUnviewed, markJobAsViewed } from "@/app/actions/jobs";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useRouter } from "next/navigation";

export const MarkAsViewAndGoNextComponent = ({
  jobId,
  nextJobId,
  isViewed,
}: {
  jobId: string;
  nextJobId: string;
  isViewed: boolean;
}) => {
    const router = useRouter();
    if (isViewed) {
      return (
        <Button variant="default" onClick={() => {
            markJobAsUnviewed(jobId).then(() => {
                router.refresh();
            })
        }}  >
            Mark as Unviewed
        </Button>
      );
    }
  return (
    <Button variant="default" asChild>
      <Link href={`/job/${nextJobId}`} onClick={() => markJobAsViewed(jobId)}>
        Mark as viewed and go to next
      </Link>
    </Button>
  );
};

export default MarkAsViewAndGoNextComponent;
