import { NextRequest, NextResponse } from 'next/server'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://aegis-trader-monitor-api:8100'

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
    })

    const data = await response.json()
    console.log(`API response status: ${response.status}, data length: ${JSON.stringify(data).length}`)

    return NextResponse.json(data, {
      status: response.status,
      headers: {
        'Cache-Control': 'no-store',
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
