/** @type {import('next').NextConfig} */
const allowedImageDomains = (process.env.NEXT_PUBLIC_IMAGE_DOMAINS || 'localhost')
  .split(',')
  .map((domain) => domain.trim())
  .filter(Boolean);

const nextConfig = {
  output: process.env.NEXT_OUTPUT_STANDALONE === 'true' ? 'standalone' : undefined,
  reactStrictMode: true,
  images: {
    domains: allowedImageDomains,
  },
  // Proxy API requests to backend if internal URL or environment variable is supplied
  async rewrites() {
    const backendUrl =
      process.env.BACKEND_INTERNAL_URL ||
      process.env.BACKEND_URL ||
      process.env.NEXT_PUBLIC_API_URL;
    if (!backendUrl) return [];
    const cleanUrl = backendUrl.replace(/\/+$/, "");
    return [
      {
        source: '/api/:path*',
        destination: `${cleanUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
