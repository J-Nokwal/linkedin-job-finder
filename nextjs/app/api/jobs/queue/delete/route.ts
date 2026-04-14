import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/config/prisma";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const queueId = body?.queueId;

    if (!queueId) {
      return NextResponse.json(
        { success: false, error: "Missing queueId" },
        { status: 400 }
      );
    }

    await prisma.applicationQueue.delete({
      where: { id: queueId },
    });

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Error deleting queue item:", error);
    return NextResponse.json(
      { success: false, error: error instanceof Error ? error.message : "Failed to delete queue item" },
      { status: 500 }
    );
  }
}
