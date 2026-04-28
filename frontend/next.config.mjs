/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static HTML/JS bundle in ./out — copied into the Python image at build
  // time and served by FastAPI under /. Does not affect `next dev`.
  output: 'export',
  images: { unoptimized: true },
  trailingSlash: false,
  // Note: ``rewrites`` is incompatible with ``output: 'export'``. The
  // frontend reaches FastAPI through ``NEXT_PUBLIC_API_BASE_URL`` instead
  // (set to http://localhost:8080 in dev, empty/same-origin in prod).
};

export default nextConfig;
