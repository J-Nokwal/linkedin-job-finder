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

function extractExternalUrls(links: Array<{ href: string; text: string }>): string[] {
  return links
    .map((link) => link.href)
    .filter((href) => !href.includes("linkedin.com"));
}

function extractLinkedInJobUrls(links: Array<{ href: string; text: string }>): string[] {
  return links
    .map((link) => link.href)
    .filter((href) => href.includes("linkedin.com/jobs"));
}

function extractLinkedInProfileUrls(links: Array<{ href: string; text: string }>): string[] {
  return links
    .map((link) => link.href)
    .filter((href) => href.includes("linkedin.com/in/"));
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Handle both single job and array of jobs
    const jobs: LinkedInJob[] = Array.isArray(body) ? body : [body];

    const createdJobs = [];

    for (const job of jobs) {
      // Parse date_posted if it exists
      let datePosted: Date | null = null;
      if (job.date_posted) {
        datePosted = new Date(job.date_posted);
      }

      // Extract URLs from links
      const externalUrls = extractExternalUrls(job.links || []);
      const linkedinJobUrls = extractLinkedInJobUrls(job.links || []);
      const linkedinProfileUrls = extractLinkedInProfileUrls(job.links || []);

      const created = await prisma.application.create({
        data: {
          postText: job.post_text || "",
          authorName: job.author_name,
          authorTitle: job.author_title,
          postUrl: job.post_url,
          datePosted: datePosted,
          likesCount: job.likes_count || 0,
          source: job.source,
          externalUrls: JSON.stringify(externalUrls),
          linkedinJobUrls: JSON.stringify(linkedinJobUrls),
          linkedinProfileUrls: JSON.stringify(linkedinProfileUrls),
          hashtagsInText: JSON.stringify(job.hashtags_in_text || []),
          scrapedAt: new Date(job.scraped_at),
          activityUrn: job.activity_urn,
          postKind: job.post_kind,
          jobRelevance: job.job_relevance_0_100,
          isFit: job.is_fit || false,
          fitScore: job.fit_score,
          fitReason: job.fit_reason,
          roleDetected: job.role_detected,
          companyDetected: job.company_detected,
          locationDetected: job.location_detected,
          employmentType: job.employment_type,
          seniority: job.seniority,
          salaryOrCompMentioned: job.salary_or_comp_mentioned,
          requirements: JSON.stringify(job.requirements || []),
          requirementsNiceToHave: JSON.stringify(job.requirements_nice_to_have || []),
          skillsMatched: JSON.stringify(job.skills_matched || []),
          skillsMissing: JSON.stringify(job.skills_missing || []),
          redFlags: JSON.stringify(job.red_flags || []),
          nextStepForCandidate: job.next_step_for_candidate,
          action: job.action,
          isViewed: false,
        },
      });

      createdJobs.push(created);
    }

    return NextResponse.json({
      success: true,
      count: createdJobs.length,
      jobs: createdJobs,
    });
  } catch (error) {
    console.error("Error saving jobs:", error);
    return NextResponse.json(
      { success: false, error: "Failed to save jobs" },
      { status: 500 }
    );
  }
}
