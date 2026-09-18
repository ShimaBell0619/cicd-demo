export async function GET() {
  return Response.json({
    status: "ok",
    service: "cicd-demo-nextjs",
  });
}
