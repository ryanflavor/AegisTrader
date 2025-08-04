import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ServiceStatusBadge } from '../service-status-badge'

describe('ServiceStatusBadge', () => {
  it('should render with ACTIVE status', () => {
    // Arrange & Act
    render(<ServiceStatusBadge status="ACTIVE" />)

    // Assert
    const badge = screen.getByText('ACTIVE')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveClass('bg-green-100', 'text-green-800')
  })

  it('should render with UNHEALTHY status', () => {
    // Arrange & Act
    render(<ServiceStatusBadge status="UNHEALTHY" />)

    // Assert
    const badge = screen.getByText('UNHEALTHY')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveClass('bg-red-100', 'text-red-800')
  })

  it('should render with STANDBY status', () => {
    // Arrange & Act
    render(<ServiceStatusBadge status="STANDBY" />)

    // Assert
    const badge = screen.getByText('STANDBY')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveClass('bg-gray-100', 'text-gray-800')
  })

  it('should accept custom className', () => {
    // Arrange & Act
    render(<ServiceStatusBadge status="ACTIVE" className="custom-class" />)

    // Assert
    const badge = screen.getByText('ACTIVE')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveClass('custom-class')
  })

  it('should apply base styling classes', () => {
    // Arrange & Act
    render(<ServiceStatusBadge status="ACTIVE" />)

    // Assert
    const badge = screen.getByText('ACTIVE')
    expect(badge).toHaveClass(
      'inline-flex',
      'items-center',
      'rounded-full',
      'px-2.5',
      'py-0.5',
      'text-xs',
      'font-semibold',
      'transition-colors'
    )
  })
})
