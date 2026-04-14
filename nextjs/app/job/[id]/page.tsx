import Link from "next/link";
import { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getJobById, getNextJobId, getPreviousJobId, markJobAsViewed } from "@/app/actions/jobs";
import MarkAsViewAndGoNextComponent from "./markAsViewComponent";

function parseJsonArray(value?: string | null): string[] {
  if (!value) {
    return [];
  }

  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed)) {
      return parsed.filter(Boolean).map(String);
    }

    return [String(parsed)];
  } catch {
    return [value];
  }
}

function formatDate(date?: Date | null) {
  if (!date) return "-";
  return new Date(date).toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function renderList(items: string[]) {
  if (!items.length) return <span className="text-muted-foreground">None</span>;
  return (
    <ul className="space-y-1 pl-5 text-muted-foreground text-sm list-disc">
      {items.map((item, index) => (
        <li key={`${item}-${index}`} className="break-words">
          {item}
        </li>
      ))}
    </ul>
  );
}

function renderLinks(items: string[]) {
  if (!items.length) return <span className="text-muted-foreground">None</span>;
  return (
    <div className="flex flex-col gap-2">
      {items.map((url, index) => (
        <a
          key={`${url}-${index}`}
          href={url}
          target="_blank"
          rel="noreferrer"
          className="text-primary text-sm underline break-all"
        >
          {url}
        </a>
      ))}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string | ReactNode }) {
  return (
    <div className="gap-1 grid">
      <div className="text-muted-foreground text-xs uppercase tracking-[0.16em]">{label}</div>
      <div className="text-foreground text-sm">{value}</div>
    </div>
  );
}

export default async function JobDetailPage({ params }: {   params: Promise<{ id: string }> }) {
  const jobId = (await params).id;
  const job = await getJobById(jobId ?? null);

  if (!job) {
    return (
      <div className="p-6">
        <Link href="/" className="text-primary underline">
          Back to jobs
        </Link>
        <h1 className="mt-4 font-bold text-2xl">Job not found</h1>
      </div>
    );
  }



  const nextJobId = await getNextJobId(job.id);
  const previousJobId = await getPreviousJobId(job.id);
  const externalUrls = parseJsonArray(job.externalUrls);
  const linkedinJobUrls = parseJsonArray(job.linkedinJobUrls);
  const linkedinProfileUrls = parseJsonArray(job.linkedinProfileUrls);
  const hashtagsInText = parseJsonArray(job.hashtagsInText);
  const requirements = parseJsonArray(job.requirements);
  const requirementsNiceToHave = parseJsonArray(job.requirementsNiceToHave);
  const skillsMatched = parseJsonArray(job.skillsMatched);
  const skillsMissing = parseJsonArray(job.skillsMissing);
  const redFlags = parseJsonArray(job.redFlags);

  return (
    <div className="p-6">
      <div className="flex flex-wrap justify-between items-center gap-3 mb-6">
        <div>
          <h1 className="font-bold text-3xl">Full Job Details</h1>
          <p className="text-muted-foreground text-sm">Review every field and navigate to the next job.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" asChild>
            <Link href="/">Back</Link>
          </Button>
          {previousJobId ? (
            <Button variant="outline" asChild>
              <Link href={`/job/${previousJobId}`}>Previous</Link>
            </Button>
          ) : (
            <Button variant="outline" disabled>
              Previous
            </Button>
          )}
          {nextJobId ? (
           <MarkAsViewAndGoNextComponent jobId={job.id} nextJobId={nextJobId} isViewed={job.isViewed} />
          ) : (
            <Button variant="default" disabled>
              Next
            </Button>
          )}
          {nextJobId ? (
            <Button variant="default" asChild>
              <Link href={`/job/${nextJobId}`}>Next</Link>
            </Button>
          ) : (
            <Button variant="default" disabled>
              Next
            </Button>
          )}
        </div>
      </div>

      <div className="gap-6 grid lg:grid-cols-[1.5fr_1fr]">
        <div className="space-y-6">
          <div className="bg-card/80 shadow-sm p-6 border rounded-lg">
            <div className="flex flex-wrap justify-between items-start gap-4">
              <div>
                <div className="flex items-center gap-3 text-muted-foreground text-sm">
                  <span>{job.companyDetected || "Unknown company"}</span>
                  <Badge variant={job.isFit ? "default" : "secondary"} className="text-xs">
                    {job.isFit ? "Fit" : "Not a fit"}
                  </Badge>
                </div>
                <h2 className="mt-2 font-semibold text-2xl">{job.roleDetected || "Unknown role"}</h2>
                <div className="text-muted-foreground text-sm">
                  {job.locationDetected || "No location"} • {job.employmentType || "No type"}
                </div>
              </div>
              <div className="space-y-2 text-right">
                <Badge variant="outline" className="text-xs">
                  {job.isViewed ? "Viewed" : "New"}
                </Badge>
                <div className="text-muted-foreground text-xs">Relevance: {job.jobRelevance ?? "—"}</div>
              </div>
            </div>

            <div className="gap-4 grid sm:grid-cols-2 mt-6">
              <DetailRow label="Seniority" value={job.seniority || "—"} />
              <DetailRow label="Salary" value={job.salaryOrCompMentioned || "—"} />
              <DetailRow label="Source" value={job.source || "—"} />
              <DetailRow label="Likes" value={String(job.likesCount || 0)} />
              <DetailRow label="Posted" value={formatDate(job.datePosted)} />
              <DetailRow label="Scraped" value={formatDate(job.scrapedAt)} />
              <DetailRow label="Post kind" value={job.postKind || "—"} />
              <DetailRow label="Action" value={job.action || "—"} />
            </div>
          </div>

          <section className="bg-card/80 shadow-sm p-6 border rounded-lg">
            <h3 className="font-semibold text-lg">Post text</h3>
            <p className="mt-3 text-foreground text-sm leading-6 whitespace-pre-wrap">
              {job.postText || "No text available."}
            </p>
          </section>

          <section className="gap-4 grid sm:grid-cols-2">
            <div className="bg-card/80 shadow-sm p-6 border rounded-lg">
              <h3 className="font-semibold text-lg">Requirements</h3>
              <div className="mt-3">{renderList(requirements)}</div>
            </div>
            <div className="bg-card/80 shadow-sm p-6 border rounded-lg">
              <h3 className="font-semibold text-lg">Nice to have</h3>
              <div className="mt-3">{renderList(requirementsNiceToHave)}</div>
            </div>
          </section>

          <section className="gap-4 grid sm:grid-cols-2">
            <div className="bg-card/80 shadow-sm p-6 border rounded-lg">
              <h3 className="font-semibold text-lg">Skills matched</h3>
              <div className="mt-3">{renderList(skillsMatched)}</div>
            </div>
            <div className="bg-card/80 shadow-sm p-6 border rounded-lg">
              <h3 className="font-semibold text-lg">Skills missing</h3>
              <div className="mt-3">{renderList(skillsMissing)}</div>
            </div>
          </section>

          <section className="bg-card/80 shadow-sm p-6 border rounded-lg">
            <h3 className="font-semibold text-lg">Red flags</h3>
            <div className="mt-3">{renderList(redFlags)}</div>
          </section>
        </div>

        <aside className="space-y-6">
          <div className="bg-card/80 shadow-sm p-6 border rounded-lg">
            <h3 className="font-semibold text-lg">Contact & links</h3>
            <div className="space-y-3 mt-4 text-foreground text-sm">
              <DetailRow label="Author name" value={job.authorName || "—"} />
              <DetailRow label="Author title" value={job.authorTitle || "—"} />
              <DetailRow label="Post URL" value={job.postUrl ? <a href={job.postUrl} target="_blank" rel="noreferrer" className="text-primary underline">{job.postUrl}</a> : "—"} />
              <DetailRow label="Activity URN" value={job.activityUrn || "—"} />
            </div>
          </div>

          <div className="bg-card/80 shadow-sm p-6 border rounded-lg">
            <h3 className="font-semibold text-lg">Links</h3>
            <div className="space-y-4 mt-3 text-sm">
              <div>
                <div className="text-muted-foreground text-xs uppercase tracking-[0.16em]">External URLs</div>
                <div className="mt-2">{renderLinks(externalUrls)}</div>
              </div>
              <div>
                <div className="text-muted-foreground text-xs uppercase tracking-[0.16em]">LinkedIn Job URLs</div>
                <div className="mt-2">{renderLinks(linkedinJobUrls)}</div>
              </div>
              <div>
                <div className="text-muted-foreground text-xs uppercase tracking-[0.16em]">LinkedIn Profiles</div>
                <div className="mt-2">{renderLinks(linkedinProfileUrls)}</div>
              </div>
            </div>
          </div>

          <div className="bg-card/80 shadow-sm p-6 border rounded-lg">
            <h3 className="font-semibold text-lg">Hashtags</h3>
            <div className="mt-3">{renderList(hashtagsInText)}</div>
          </div>

          <div className="bg-card/80 shadow-sm p-6 border rounded-lg">
            <h3 className="font-semibold text-lg">Fit details</h3>
            <div className="space-y-3 mt-4 text-foreground text-sm">
              <DetailRow label="Fit score" value={job.fitScore != null ? `${job.fitScore}%` : "—"} />
              <DetailRow label="Fit reason" value={job.fitReason || "—"} />
              <DetailRow label="Next step" value={job.nextStepForCandidate || "—"} />
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
