/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone", // for the Docker image (infra/docker/web.Dockerfile)
  eslint: { ignoreDuringBuilds: true }, // type-check via tsc; eslint flat-config is a follow-up
  // Next.js 15 default proxy timeout is 30s, but Qwen2.5-14B can take 40-60s on GB10 for
  // long answers — without this, slow chats bubble up to the browser as HTTP 500 even
  // though the API finished successfully. 180s; real fix is SSE streaming (deferred).
  experimental: { proxyTimeout: 180_000 },
  async rewrites() {
    // Same-origin proxy so the browser never hits the API cross-origin (no CORS).
    // NOTE: Next bakes rewrite destinations into the build manifest, so API_PROXY_TARGET
    // must be set at BUILD time (web.Dockerfile ARG). Defaults to localhost for `next dev`.
    const target = process.env.API_PROXY_TARGET || "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${target}/api/:path*` }];
  },
};

export default nextConfig;
