import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/config/prisma";
import * as fs from "fs";
import * as path from "path";

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

function getResultsDir(): string {
  // Navigate from nextjs/app/api/jobs/load to the project root, then to results
  const rootDir = path.join(process.cwd(), "..");
  const resultsDir = path.join(rootDir, "results");
  return path.resolve(resultsDir);
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { filePath } = body;

    let jobs: LinkedInJob[];

    if (filePath) {
      // Load from specific file
      const fullPath = path.join(process.cwd(), "..", "..", filePath);
      const fileContent = fs.readFileSync(fullPath, "utf-8");
      jobs = JSON.parse(fileContent);
    } else {
      // Load all JSON files from results folder
      const resultsDir = getResultsDir();
      jobs = [];

      if (fs.existsSync(resultsDir)) {
        const files = fs.readdirSync(resultsDir).filter((f) => f.endsWith(".json"));
        for (const file of files) {
          const filePath = path.join(resultsDir, file);
          // console.log("file found", filePath)
          const fileContent = fs.readFileSync(filePath, "utf-8");
          // console.log("fileContent", fileContent)
          const fileJobs = JSON.parse(fileContent);
          jobs.push(...(Array.isArray(fileJobs) ? fileJobs : [fileJobs]));
        }
      }
    }
    
    if (!Array.isArray(jobs)) {
      jobs = [jobs];
    }
    
    const createdJobs: { id: string; postText: string; authorName: string | null; authorTitle: string | null; postUrl: string | null; datePosted: Date | null; likesCount: number; source: string | null; externalUrls: string | null; linkedinJobUrls: string | null; linkedinProfileUrls: string | null; hashtagsInText: string | null; scrapedAt: Date; activityUrn: string | null; postKind: string | null; jobRelevance: number | null; isFit: boolean; fitScore: number | null; fitReason: string | null; roleDetected: string | null; companyDetected: string | null; locationDetected: string | null; employmentType: string | null; seniority: string | null; salaryOrCompMentioned: string | null; requirements: string | null; requirementsNiceToHave: string | null; skillsMatched: string | null; skillsMissing: string | null; redFlags: string | null; nextStepForCandidate: string | null; action: string | null; isViewed: boolean; createdAt: Date; updatedAt: Date; }[] = [];
    
    for (const job of jobs) {
      // console.log("---------------","job")
      // Skip if already exists (check by scraped_at + post_text combination)
      const existing = await prisma.application.findFirst({
        where: {
          scrapedAt: new Date(job.scraped_at),
          postText: job.post_text,
        },
      });

      if (existing) {
        continue;
      }
      // Parse date_posted if it exists
      let datePosted: Date | null = null;
      if (job.date_posted) {
        const parsed = new Date(job.date_posted);
        if (!isNaN(parsed.getTime())) {
          datePosted = parsed;
        }
      }

      // Extract URLs from links if links exist
      const externalUrls = job.links ? extractExternalUrls(job.links) : job.external_urls || [];
      const linkedinJobUrls = job.links ? extractLinkedInJobUrls(job.links) : job.linkedin_job_urls || [];
      const linkedinProfileUrls = job.links ? extractLinkedInProfileUrls(job.links) : job.linkedin_profile_urls || [];

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
    console.error("Error loading jobs:", error);
    return NextResponse.json(
      { success: false, error: error instanceof Error ? error.message : "Failed to load jobs" },
      { status: 500 }
    );
  }
}
