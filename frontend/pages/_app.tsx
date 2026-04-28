import { ClerkProvider } from "@clerk/nextjs";
import type { AppProps } from "next/app";
import "../styles/globals.css";

// Clerk dev-instance keys are read at build time by Next.js (NEXT_PUBLIC_*).
// Pages are rendered as static HTML; auth state is hydrated client-side.
export default function CounselAIApp({ Component, pageProps }: AppProps) {
  return (
    <ClerkProvider {...pageProps}>
      <Component {...pageProps} />
    </ClerkProvider>
  );
}
