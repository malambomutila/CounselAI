import { Html, Head, Main, NextScript } from "next/document";

// Static-export-safe document. The <title> can't live here per Next.js's
// rules (must be in pages/ via next/head), so each page sets its own. The
// favicon and brand-level meta tags do live here because they apply to
// every route — including 404 and any future routes.
export default function Document() {
  return (
    <Html lang="en">
      <Head>
        <meta name="description" content="Five AI legal specialists analyse your case from every angle." />
        <meta name="application-name" content="CounselAI" />
        <meta name="apple-mobile-web-app-title" content="CounselAI" />
        <meta name="theme-color" content="#0F52FF" />
        <link rel="icon" type="image/x-icon" href="/favicon.ico" />
        <link rel="shortcut icon" href="/favicon.ico" />
        <link rel="apple-touch-icon" href="/favicon.ico" />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
