"use server";

import prisma from "@/lib/config/prisma";
import { ApplicationQueue } from "@/lib/client-generated/prisma/client";

export async function getPendingQueueItems(page = 0, pageSize = 100): Promise<ApplicationQueue[]> {
  try {
    return prisma.applicationQueue.findMany({
      where: {
        status: {
          not: "done",
        },
        processedAt: null,
      },
      orderBy: [{ scrapedAt: "desc" }, { createdAt: "asc" }],
      skip: page * pageSize,
      take: pageSize,
    });
  } catch (error) {
    console.error("Error fetching pending queue items:", error);
    return [];
  }
}

export async function countPendingQueueItems(): Promise<number> {
  try {
    return prisma.applicationQueue.count({
      where: {
        status: {
          not: "done",
        },
        processedAt: null,
      },
    });
  } catch (error) {
    console.error("Error counting pending queue items:", error);
    return 0;
  }
}

export async function deleteQueueItem(id: string): Promise<{ success: boolean; error?: string }> {
  try {
    await prisma.applicationQueue.delete({
      where: { id },
    });

    return { success: true };
  } catch (error) {
    console.error("Error deleting queue item:", error);
    return { success: false, error: "Failed to delete queue item" };
  }
}
