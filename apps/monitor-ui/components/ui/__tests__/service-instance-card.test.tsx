import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { useRouter } from 'next/navigation'
import { ServiceInstanceCard } from '../service-instance-card'
import type { ServiceInstance } from '@/types/service'

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}))

const mockPush = jest.fn()

const mockInstance: ServiceInstance = {
  service_name: 'test-service',
  instance_id: 'test-instance-01',
  version: '1.0.0',
  status: 'ACTIVE',
  last_heartbeat: new Date().toISOString(),
  sticky_active_group: null,
  metadata: {}
}

describe('ServiceInstanceCard', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
    })
  })

  it('should render service instance information', () => {
    // Arrange & Act
    render(<ServiceInstanceCard instance={mockInstance} />)

    // Assert
    expect(screen.getByText('test-service')).toBeInTheDocument()
    expect(screen.getByText('test-instance-01')).toBeInTheDocument()
    expect(screen.getByText('1.0.0')).toBeInTheDocument()
    expect(screen.getByText('Instance ID:')).toBeInTheDocument()
    expect(screen.getByText('Version:')).toBeInTheDocument()
    expect(screen.getByText('Last Heartbeat:')).toBeInTheDocument()
  })

  it('should format last heartbeat time correctly', () => {
    // Arrange
    const now = new Date()
    const testCases = [
      { offset: 0, expected: /0s ago/ },
      { offset: 30, expected: /30s ago/ },
      { offset: 90, expected: /1m ago/ },
      { offset: 3600, expected: /1h ago/ },
    ]

    testCases.forEach(({ offset, expected }) => {
      // Act
      const heartbeat = new Date(now.getTime() - offset * 1000)
      const instance = { ...mockInstance, last_heartbeat: heartbeat.toISOString() }
      const { unmount } = render(<ServiceInstanceCard instance={instance} />)

      // Assert
      expect(screen.getByText(expected)).toBeInTheDocument()
      unmount()
    })
  })

  it('should handle click navigation', () => {
    // Arrange & Act
    render(<ServiceInstanceCard instance={mockInstance} />)
    const card = screen.getByText('test-service').closest('div[class*="bg-white"]')

    fireEvent.click(card!)

    // Assert
    expect(mockPush).toHaveBeenCalledWith('/services/test-instance-01')
  })

  it('should display correct status badge', () => {
    // Arrange
    const statusVariants = [
      { status: 'ACTIVE' as const, expectedClass: 'bg-green-100' },
      { status: 'UNHEALTHY' as const, expectedClass: 'bg-red-100' },
      { status: 'STANDBY' as const, expectedClass: 'bg-gray-100' },
    ]

    statusVariants.forEach(({ status, expectedClass }) => {
      // Act
      const instance = { ...mockInstance, status }
      const { unmount } = render(<ServiceInstanceCard instance={instance} />)

      // Assert
      const badge = screen.getByText(status)
      expect(badge).toHaveClass(expectedClass)
      unmount()
    })
  })

  it('should accept custom className', () => {
    // Arrange & Act
    render(<ServiceInstanceCard instance={mockInstance} className="custom-class" />)

    // Assert
    const card = screen.getByText('test-service').closest('div[class*="bg-white"]')
    expect(card).toHaveClass('custom-class')
  })

  it('should apply default styling classes', () => {
    // Arrange & Act
    render(<ServiceInstanceCard instance={mockInstance} />)

    // Assert
    const card = screen.getByText('test-service').closest('div[class*="bg-white"]')
    expect(card).toHaveClass(
      'bg-white',
      'rounded-lg',
      'shadow-md',
      'p-6',
      'hover:shadow-lg',
      'transition-shadow',
      'cursor-pointer'
    )
  })
})
