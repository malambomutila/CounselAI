import Head from "next/head";
import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/router";
import { SignInButton, SignedIn, SignedOut, useAuth } from "@clerk/nextjs";

// Landing / sign-in page. Authed users get bounced to /app immediately.
export default function Landing() {
  const router = useRouter();
  const { isSignedIn, isLoaded } = useAuth();

  useEffect(() => {
    if (isLoaded && isSignedIn) {
      router.replace("/app");
    }
  }, [isLoaded, isSignedIn, router]);

  return (
    <>
      <Head>
        <title>CounselAI</title>
      </Head>
      <main className="min-h-screen flex flex-col items-center justify-center bg-canvas px-6 py-16">
        <div className="max-w-2xl text-center">
          <h1 className="font-display font-semibold text-[56px] leading-none tracking-[-0.025em] mb-6">
            CounselAI
          </h1>
          <p className="text-ink-muted text-lg leading-relaxed mb-10 max-w-xl mx-auto">
            Five AI legal specialists analyse your case from every angle so you
            walk into proceedings fully prepared. Sign in to begin.
          </p>

          <SignedOut>
            <SignInButton mode="modal">
              <button className="cta-primary text-base px-10 py-3">
                Sign in to continue
              </button>
            </SignInButton>
          </SignedOut>

          <SignedIn>
            <Link href="/app" className="cta-primary inline-block text-base px-10 py-3 no-underline">
              Continue to the app →
            </Link>
          </SignedIn>

          <p className="disclaimer mt-12 max-w-md mx-auto">
            For legal research only. Not legal advice and not a substitute for
            a licensed practitioner.
          </p>
        </div>
      </main>
    </>
  );
}
