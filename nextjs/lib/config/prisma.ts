import { PrismaBetterSqlite3 } from "@prisma/adapter-better-sqlite3";
import { PrismaClient } from "../client-generated/prisma/client";
import * as path from "path";


const prisma = new PrismaClient({
  adapter: new PrismaBetterSqlite3(
    { url: process.env.DATABASE_URL },
    { timestampFormat: "unixepoch-ms" },
  ),
});



export default prisma;
