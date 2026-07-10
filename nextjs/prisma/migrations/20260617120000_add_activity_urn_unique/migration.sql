-- Deduplicate existing Application rows: keep the first-inserted row per activityUrn.
-- Without this, CREATE UNIQUE INDEX would fail if duplicates already exist.
DELETE FROM "Application"
WHERE "activityUrn" IS NOT NULL
  AND "rowid" NOT IN (
    SELECT MIN("rowid")
    FROM "Application"
    WHERE "activityUrn" IS NOT NULL
    GROUP BY "activityUrn"
  );

-- CreateUniqueIndex
CREATE UNIQUE INDEX "Application_activityUrn_key" ON "Application"("activityUrn");

-- AddColumn: store activityUrn on queue rows for faster dedup lookups
ALTER TABLE "ApplicationQueue" ADD COLUMN "activityUrn" TEXT;
