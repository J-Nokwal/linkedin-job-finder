import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/config/prisma";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Accept either a single queueId or an array of queueIds.
    const ids: string[] =
      body?.queueIds ?? (body?.queueId ? [body.queueId] : []);

    if (!ids.length) {
      return NextResponse.json(
        { success: false, error: "Missing queueId or queueIds" },
        { status: 400 }
      );
    }

    const { count } = await prisma.applicationQueue.deleteMany({
      where: { id: { in: ids } },
    });

    return NextResponse.json({ success: true, deleted: count });
  } catch (error) {
    console.error("Error deleting queue item(s):", error);
    return NextResponse.json(
      { success: false, error: error instanceof Error ? error.message : "Failed to delete" },
      { status: 500 }
    );
  }
}
