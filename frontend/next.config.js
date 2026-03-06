/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  async rewrites() {
    return process.env.NODE_ENV === 'development'
      ? [{ source: '/api/proxy/:path*', destination: 'http://localhost:8000/api/:path*' }]
      : [];
  },
};

module.exports = nextConfig;
