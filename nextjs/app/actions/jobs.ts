"use server";

import prisma from "@/lib/config/prisma";
import { Application } from "@/lib/client-generated/prisma/client";

export async function getJobsByDate(date: string): Promise<Application[]> {
  try {
    // Parse the date and create start and end of day in UTC
    const startDate = new Date(date);
    const endDate = new Date(date);
    endDate.setDate(endDate.getDate() + 1);

    const jobs = await prisma.application.findMany({
      where: {
        scrapedAt: {
          gte: startDate,
          lt: endDate,
        },
      },
      orderBy: {
        scrapedAt: "desc",
      },
    });

    return jobs;
  } catch (error) {
    console.error("Error fetching jobs by date:", error);
    return [];
  }
}

export async function getJobById(id?: string | null): Promise<Application | null> {
  if (!id) {
    return null;
  }

  try {
    return prisma.application.findUnique({
      where: { id },
    });
  } catch (error) {
    console.error("Error fetching job by id:", error);
    return null;
  }
}

export async function getNextJobId(id: string): Promise<string | null> {
  try {
    const jobs = await prisma.application.findMany({
      select: { id: true },
      orderBy: [{ scrapedAt: "desc" }, { id: "asc" }],
    });

    const index = jobs.findIndex((job) => job.id === id);
    return jobs[index + 1]?.id ?? null;
  } catch (error) {
    console.error("Error fetching next job id:", error);
    return null;
  }
}

export async function getPreviousJobId(id: string): Promise<string | null> {
  try {
    const jobs = await prisma.application.findMany({
      select: { id: true },
      orderBy: [{ scrapedAt: "desc" }, { id: "asc" }],
    });

    const index = jobs.findIndex((job) => job.id === id);
    return jobs[index - 1]?.id ?? null;
  } catch (error) {
    console.error("Error fetching previous job id:", error);
    return null;
  }
}

export async function getJobsByDateRange(startDate: string, endDate: string): Promise<Application[]> {
  try {
    const start = new Date(startDate);
    const end = new Date(endDate);
    end.setDate(end.getDate() + 1);

    const jobs = await prisma.application.findMany({
      where: {
        scrapedAt: {
          gte: start,
          lt: end,
        },
      },
      orderBy: {
        scrapedAt: "desc",
      },
    });

    return jobs;
  } catch (error) {
    console.error("Error fetching jobs by date range:", error);
    return [];
  }
}

export async function getAllJobs(): Promise<Application[]> {
  try {
    const jobs = await prisma.application.findMany({
      orderBy: {
        scrapedAt: "desc",
      },
    });

    return jobs;
  } catch (error) {
    console.error("Error fetching all jobs:", error);
    return [];
  }
}

export async function markJobAsViewed(id: string): Promise<{ success: boolean; error?: string }> {
  try {
    await prisma.application.update({
      where: { id },
      data: { isViewed: true },
    });

    return { success: true };
  } catch (error) {
    console.error("Error marking job as viewed:", error);
    return { success: false, error: "Failed to mark job as viewed" };
  }
}

export async function markJobAsUnviewed(id: string): Promise<{ success: boolean; error?: string }> {
  try {
    await prisma.application.update({
      where: { id },
      data: { isViewed: false },
    });

    return { success: true };
  } catch (error) {
    console.error("Error marking job as unviewed:", error);
    return { success: false, error: "Failed to mark job as unviewed" };
  }
}

export async function toggleJobViewed(id: string, currentStatus: boolean): Promise<{ success: boolean; error?: string }> {
  try {
    await prisma.application.update({
      where: { id },
      data: { isViewed: !currentStatus },
    });

    return { success: true };
  } catch (error) {
    console.error("Error toggling job viewed status:", error);
    return { success: false, error: "Failed to toggle job viewed status" };
  }
}

export async function saveJob(jobData: Omit<Application, "id" | "createdAt" | "updatedAt">): Promise<{ success: boolean; error?: string; jobId?: string }> {
  try {
    const created = await prisma.application.create({
      data: jobData,
    });

    return { success: true, jobId: created.id };
  } catch (error) {
    console.error("Error saving job:", error);
    return { success: false, error: "Failed to save job" };
  }
}

export async function bulkSaveJobs(jobsData: Omit<Application, "id" | "createdAt" | "updatedAt">[]): Promise<{ success: boolean; count?: number; error?: string }> {
  try {
    let count = 0;
    for (const jobData of jobsData) {
      await prisma.application.create({
        data: jobData,
      });
      count++;
    }

    return { success: true, count };
  } catch (error) {
    console.error("Error bulk saving jobs:", error);
    return { success: false, error: "Failed to bulk save jobs" };
  }
}

export async function deleteJob(id: string): Promise<{ success: boolean; error?: string }> {
  try {
    await prisma.application.delete({
      where: { id },
    });

    return { success: true };
  } catch (error) {
    console.error("Error deleting job:", error);
    return { success: false, error: "Failed to delete job" };
  }
}

export async function searchJobs(query: string): Promise<Application[]> {
  try {
    if (!query.trim()) {
      return [];
    }

    const searchTerms = query.toLowerCase().split(/\s+/).filter(Boolean);

    // Build filter conditions for each search term
    const whereConditions = searchTerms.map((term) => ({
      OR: [
        { companyDetected: { contains: term, mode: "insensitive" as const } },
        { roleDetected: { contains: term, mode: "insensitive" as const } },
        { locationDetected: { contains: term, mode: "insensitive" as const } },
        { postText: { contains: term, mode: "insensitive" as const } },
        { seniority: { contains: term, mode: "insensitive" as const } },
        { employmentType: { contains: term, mode: "insensitive" as const } },
        { salaryOrCompMentioned: { contains: term, mode: "insensitive" as const } },
        { requirements: { contains: term, mode: "insensitive" as const } },
        { skillsMatched: { contains: term, mode: "insensitive" as const } },
        { hashtagsInText: { contains: term, mode: "insensitive" as const } },
      ],
    }));

    const jobs = await prisma.application.findMany({
      where: {
        AND: whereConditions,
      },
      orderBy: {
        scrapedAt: "desc",
      },
    });

    return jobs;
  } catch (error) {
    console.error("Error searching jobs:", error);
    return [];
  }
}
