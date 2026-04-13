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

function parseScrapedAt(value: string | null): Date {
  const date = value ? new Date(value) : new Date();
  return isNaN(date.getTime()) ? new Date() : date;
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const jobs: LinkedInJob[] = Array.isArray(body) ? body : [body];

    let added = 0;
    let skipped = 0;

    for (const job of jobs) {
      const postText = job.post_text || "";
      const scrapedAt = parseScrapedAt(job.scraped_at);

      const existingQueue = await prisma.applicationQueue.findFirst({
        where: {
          postText,
          scrapedAt,
        },
      });

      const existingApp = await prisma.application.findFirst({
        where: {
          postText,
          scrapedAt,
        },
      });

      if (existingQueue || existingApp) {
        skipped += 1;
        continue;
      }

      await prisma.applicationQueue.create({
        data: {
          payload: JSON.stringify(job),
          postText,
          scrapedAt,
          source: job.source,
          postUrl: job.post_url,
          status: "pending",
        },
      });

      added += 1;
    }

    return NextResponse.json({
      success: true,
      added,
      skipped,
    });
  } catch (error) {
    console.error("Error enqueuing jobs:", error);
    return NextResponse.json(
      { success: false, error: error instanceof Error ? error.message : "Failed to enqueue jobs" },
      { status: 500 }
    );
  }
}
