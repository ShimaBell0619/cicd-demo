export default function Home() {
  return (
    <main>
      <p className="eyebrow">Azure Pipelines CI/CD Demo</p>
      <h1>Build once. Promote the same artifact.</h1>
      <p>
        This minimal Next.js application is the deployment target for the
        dev → uat → prod → dr pipeline demo.
      </p>
      <a href="/api/health">Health endpoint</a>
    </main>
  );
}
