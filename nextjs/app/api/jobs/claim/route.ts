import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/config/prisma";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const maxItems = Number(body?.maxItems ?? 5);
    const workerId = typeof body?.workerId === "string" ? body.workerId : `worker-${Date.now()}`;
    const staleThreshold = new Date(Date.now() - 10 * 60 * 1000);

    const pendingItems = await prisma.applicationQueue.findMany({
      where: {
        OR: [
          { status: "pending" },
          { status: "processing", lockedAt: { lt: staleThreshold } },
        ],
      },
      orderBy: [{ scrapedAt: "desc" }, { createdAt: "asc" }],
      take: maxItems,
    });

    if (!pendingItems.length) {
      return NextResponse.json({ success: true, items: [] });
    }

    const claimedItems = await prisma.$transaction(
      pendingItems.map((item) =>
        prisma.applicationQueue.update({
          where: { id: item.id },
          data: {
            status: "processing",
            lockedAt: new Date(),
            workerId,
            attemptCount: item.attemptCount + 1,
          },
        })
      )
    );

    return NextResponse.json({ success: true, items: claimedItems });
  } catch (error) {
    console.error("Error claiming queue jobs:", error);
    return NextResponse.json(
      { success: false, error: error instanceof Error ? error.message : "Failed to claim jobs" },
      { status: 500 }
    );
  }
}
