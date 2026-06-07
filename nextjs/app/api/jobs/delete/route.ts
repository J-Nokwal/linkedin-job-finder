import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/config/prisma";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const ids = body?.ids;

    if (!Array.isArray(ids) || ids.length === 0) {
      return NextResponse.json(
        { success: false, error: "Missing job ids to delete" },
        { status: 400 }
      );
    }

    const result = await prisma.application.deleteMany({
      where: {
        id: {
          in: ids,
        },
      },
    });

    return NextResponse.json({ success: true, deletedCount: result.count });
  } catch (error) {
    console.error("Error deleting jobs:", error);
    return NextResponse.json(
      { success: false, error: error instanceof Error ? error.message : "Failed to delete jobs" },
      { status: 500 }
    );
  }
}
