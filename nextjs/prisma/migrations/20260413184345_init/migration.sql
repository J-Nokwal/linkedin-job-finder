-- CreateTable
CREATE TABLE "Application" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "postText" TEXT NOT NULL,
    "authorName" TEXT,
    "authorTitle" TEXT,
    "postUrl" TEXT,
    "datePosted" DATETIME,
    "likesCount" INTEGER NOT NULL DEFAULT 0,
    "source" TEXT,
    "externalUrls" TEXT,
    "linkedinJobUrls" TEXT,
    "linkedinProfileUrls" TEXT,
    "hashtagsInText" TEXT,
    "scrapedAt" DATETIME NOT NULL,
    "activityUrn" TEXT,
    "postKind" TEXT,
    "jobRelevance" INTEGER,
    "isFit" BOOLEAN NOT NULL DEFAULT false,
    "fitScore" INTEGER,
    "fitReason" TEXT,
    "roleDetected" TEXT,
    "companyDetected" TEXT,
    "locationDetected" TEXT,
    "employmentType" TEXT,
    "seniority" TEXT,
    "salaryOrCompMentioned" TEXT,
    "requirements" TEXT,
    "requirementsNiceToHave" TEXT,
    "skillsMatched" TEXT,
    "skillsMissing" TEXT,
    "redFlags" TEXT,
    "nextStepForCandidate" TEXT,
    "action" TEXT,
    "isViewed" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "ApplicationQueue" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "payload" JSONB NOT NULL,
    "postText" TEXT NOT NULL,
    "scrapedAt" DATETIME NOT NULL,
    "source" TEXT,
    "postUrl" TEXT,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "attemptCount" INTEGER NOT NULL DEFAULT 0,
    "workerId" TEXT,
    "lockedAt" DATETIME,
    "processedAt" DATETIME,
    "appId" TEXT,
    "errorMessage" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateIndex
CREATE INDEX "Application_datePosted_idx" ON "Application"("datePosted");

-- CreateIndex
CREATE INDEX "Application_isViewed_idx" ON "Application"("isViewed");

-- CreateIndex
CREATE INDEX "Application_companyDetected_idx" ON "Application"("companyDetected");

-- CreateIndex
CREATE INDEX "ApplicationQueue_status_idx" ON "ApplicationQueue"("status");

-- CreateIndex
CREATE INDEX "ApplicationQueue_scrapedAt_idx" ON "ApplicationQueue"("scrapedAt");

-- CreateIndex
CREATE INDEX "ApplicationQueue_workerId_idx" ON "ApplicationQueue"("workerId");
