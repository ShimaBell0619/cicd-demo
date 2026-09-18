import { releaseInfo } from "../../release-info.generated";

export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json(
    {
      status: "ok",
      service: "cicd-demo-nextjs",
      environment: process.env.APP_ENV ?? "unknown",
      version: releaseInfo.version,
      commitSha: releaseInfo.commitSha,
      buildId: releaseInfo.buildId,
    },
    {
      status: 200,
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}
