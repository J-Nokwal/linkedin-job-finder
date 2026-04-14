/* eslint-disable @typescript-eslint/no-explicit-any */
import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/config/prisma";

interface LinkedInJob {
  post_text: string;
  author_name: string | null;
  author_title: string | null;
  post_url: string | null;
  date_posted: string | null;
  likes_count: number;
  source: string | null;
  links: Array<{ href: string; text: string }>;
  external_urls: string[];
  linkedin_job_urls: string[];
  linkedin_profile_urls: string[];
  hashtags_in_text: string[];
  scraped_at: string;
  activity_urn: string | null;
  post_kind: string | null;
  job_relevance_0_100: number | null;
  is_fit: boolean;
  fit_score: number | null;
  fit_reason: string | null;
  role_detected: string | null;
  company_detected: string | null;
  location_detected: string | null;
  employment_type: string | null;
  seniority: string | null;
  salary_or_comp_mentioned: string | null;
  requirements: string[];
  requirements_nice_to_have: string[];
  apply_links_ranked: Array<{ href: string; text: string }> | string[];
  apply_link?: { href: string; text: string };
  skills_matched: string[];
  skills_missing: string[];
  red_flags: string[];
  next_step_for_candidate: string | null;
  action: string | null;
}

function extractExternalUrls(links: Array<{ href: string; text: string }> = []): string[] {
  return links.map((link) => link.href).filter((href) => !href.includes("linkedin.com"));
}

function extractLinkedInJobUrls(links: Array<{ href: string; text: string }> = []): string[] {
  return links.map((link) => link.href).filter((href) => href.includes("linkedin.com/jobs"));
}

function extractLinkedInProfileUrls(links: Array<{ href: string; text: string }> = []): string[] {
  return links.map((link) => link.href).filter((href) => href.includes("linkedin.com/in/"));
}

function parseDate(value: string | Date | null | undefined): Date | null {
  if (value == null || value === "") {
    return null;
  }

  const date = value instanceof Date ? value : new Date(value);
  return isNaN(date.getTime()) ? null : date;
}

function parseScrapedAt(value: string | Date | null | undefined): Date {
  const date = parseDate(value);
  return date ?? new Date();
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const queueId = body?.queueId;
    const analyzedJob: LinkedInJob = body?.analyzedJob;

    if (!queueId || !analyzedJob) {
      return NextResponse.json(
        { success: false, error: "Missing queueId or analyzedJob" },
        { status: 400 }
      );
    }

    const queueItem = await prisma.applicationQueue.findUnique({
      where: { id: queueId },
    });

    if (!queueItem) {
      return NextResponse.json(
        { success: false, error: "Queue item not found" },
        { status: 404 }
      );
    }

    const postText = analyzedJob.post_text || "";
    const scrapedAt = parseScrapedAt(analyzedJob.scraped_at);
    const datePosted = parseDate(analyzedJob.date_posted);
    const externalUrls = extractExternalUrls(analyzedJob.links || analyzedJob.external_urls || [] as any);
    const linkedinJobUrls = extractLinkedInJobUrls(analyzedJob.links || analyzedJob.linkedin_job_urls || [] as any);
    const linkedinProfileUrls = extractLinkedInProfileUrls(analyzedJob.links || analyzedJob.linkedin_profile_urls || [] as any);

    let application = await prisma.application.findFirst({
      where: {
        postText,
        scrapedAt,
      },
    });

    if (!application) {
      application = await prisma.application.create({
        data: {
          postText,
          authorName: analyzedJob.author_name,
          authorTitle: analyzedJob.author_title,
          postUrl: analyzedJob.post_url,
          datePosted,
          likesCount: analyzedJob.likes_count || 0,
          source: analyzedJob.source,
          externalUrls: JSON.stringify(externalUrls),
          linkedinJobUrls: JSON.stringify(linkedinJobUrls),
          linkedinProfileUrls: JSON.stringify(linkedinProfileUrls),
          hashtagsInText: JSON.stringify(analyzedJob.hashtags_in_text || []),
          scrapedAt,
          activityUrn: analyzedJob.activity_urn,
          postKind: analyzedJob.post_kind,
          jobRelevance: analyzedJob.job_relevance_0_100,
          isFit: analyzedJob.is_fit || false,
          fitScore: analyzedJob.fit_score,
          fitReason: analyzedJob.fit_reason,
          roleDetected: analyzedJob.role_detected,
          companyDetected: analyzedJob.company_detected,
          locationDetected: analyzedJob.location_detected,
          employmentType: analyzedJob.employment_type,
          seniority: analyzedJob.seniority,
          salaryOrCompMentioned: analyzedJob.salary_or_comp_mentioned,
          requirements: JSON.stringify(analyzedJob.requirements || []),
          requirementsNiceToHave: JSON.stringify(analyzedJob.requirements_nice_to_have || []),
          skillsMatched: JSON.stringify(analyzedJob.skills_matched || []),
          skillsMissing: JSON.stringify(analyzedJob.skills_missing || []),
          redFlags: JSON.stringify(analyzedJob.red_flags || []),
          nextStepForCandidate: analyzedJob.next_step_for_candidate,
          action: analyzedJob.action,
          isViewed: false,
        },
      });
    }

    await prisma.applicationQueue.update({
      where: { id: queueId },
      data: {
        status: "done",
        processedAt: new Date(),
        appId: application.id,
      },
    });

    return NextResponse.json({ success: true, jobId: application.id });
  } catch (error) {
    console.error("Error completing queued job:", error);
    return NextResponse.json(
      { success: false, error: error instanceof Error ? error.message : "Failed to complete queued job" },
      { status: 500 }
    );
  }
}
