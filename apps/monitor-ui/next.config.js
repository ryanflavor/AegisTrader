/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  typescript: {
    // Allow production builds to succeed even with type errors
    ignoreBuildErrors: false,
  },
  eslint: {
    // Allow production builds to succeed even with ESLint errors
    ignoreDuringBuilds: false,
  },
}

module.exports = nextConfig