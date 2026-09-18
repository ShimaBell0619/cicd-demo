import "./globals.css";

export const metadata = {
  title: "Azure Pipelines CI/CD Demo",
  description: "Next.js deployment target for the cicd-demo repository",
};

export default function RootLayout({ children }) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
