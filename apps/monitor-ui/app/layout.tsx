import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'AegisTrader Monitor',
  description: 'Monitoring UI for AegisTrader system',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}