import { NextRequest, NextResponse } from 'next/server'

// Use runtime environment variable (not NEXT_PUBLIC_ which is build-time)
// This ensures the server-side proxy uses the correct internal K8s service URL
const API_BASE_URL = process.env.API_URL || 'http://aegis-trader-monitor-api:8100'

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const path = params.path.join('/')

  // Special handling for endpoints that don't have /api prefix
  const noApiPrefixEndpoints = ['health', 'status', 'ready']
  const firstSegment = params.path[0]

  let apiUrl: string
  if (noApiPrefixEndpoints.includes(firstSegment)) {
    // These endpoints are at the root level
    apiUrl = `${API_BASE_URL}/${path}`
  } else {
    // All other endpoints have /api prefix
    apiUrl = `${API_BASE_URL}/api/${path}`
  }

  console.log(`Proxying request to: ${apiUrl}`)

  try {
    const response = await fetch(apiUrl, {
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    })

    const data = await response.json()
    console.log(`API response status: ${response.status}, data length: ${JSON.stringify(data).length}`)

    return NextResponse.json(data, {
      status: response.status,
      headers: {
        'Cache-Control': 'no-store, no-cache, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
      },
    })
  } catch (error) {
    console.error('API proxy error:', error)
    console.error(`Failed to fetch from: ${apiUrl}`)
    return NextResponse.json(
      { error: 'Failed to connect to API' },
      { status: 500 }
    )
  }
}
