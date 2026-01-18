import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QASettingsPopover } from './QASettingsPopover'
import { QA_DEFAULTS } from '../config/qa'

describe('QASettingsPopover', () => {
  const defaultSettings = { ...QA_DEFAULTS }
  const mockOnChange = vi.fn()

  beforeEach(() => {
    mockOnChange.mockClear()
  })

  it('renders gear icon button', () => {
    render(
      <QASettingsPopover settings={defaultSettings} onChange={mockOnChange} />
    )
    expect(screen.getByRole('button', { name: /settings/i })).toBeInTheDocument()
  })

  it('opens popover on click', () => {
    render(
      <QASettingsPopover settings={defaultSettings} onChange={mockOnChange} />
    )
    fireEvent.click(screen.getByRole('button', { name: /settings/i }))
    expect(screen.getByText('Answer Settings')).toBeInTheDocument()
  })

  it('calls onChange when quick mode toggled', () => {
    render(
      <QASettingsPopover settings={defaultSettings} onChange={mockOnChange} />
    )
    fireEvent.click(screen.getByRole('button', { name: /settings/i }))
    fireEvent.click(screen.getByLabelText(/thorough/i))
    expect(mockOnChange).toHaveBeenCalledWith(
      expect.objectContaining({ quickMode: false })
    )
  })

  it('closes popover when close button clicked', () => {
    render(
      <QASettingsPopover settings={defaultSettings} onChange={mockOnChange} />
    )
    fireEvent.click(screen.getByRole('button', { name: /settings/i }))
    expect(screen.getByText('Answer Settings')).toBeInTheDocument()

    // Find the close button (X icon) and click it
    const closeButton = screen.getByRole('button', { name: /close/i })
    fireEvent.click(closeButton)
    expect(screen.queryByText('Answer Settings')).not.toBeInTheDocument()
  })

  it('calls onChange when temperature slider changed', () => {
    render(
      <QASettingsPopover settings={defaultSettings} onChange={mockOnChange} />
    )
    fireEvent.click(screen.getByRole('button', { name: /settings/i }))

    const temperatureSlider = screen.getByRole('slider', { name: /temperature/i })
    fireEvent.change(temperatureSlider, { target: { value: '0.8' } })

    expect(mockOnChange).toHaveBeenCalledWith(
      expect.objectContaining({ temperature: 0.8 })
    )
  })

  it('calls onChange when timeout slider changed', () => {
    render(
      <QASettingsPopover settings={defaultSettings} onChange={mockOnChange} />
    )
    fireEvent.click(screen.getByRole('button', { name: /settings/i }))

    const timeoutSlider = screen.getByRole('slider', { name: /timeout/i })
    fireEvent.change(timeoutSlider, { target: { value: '5' } })

    expect(mockOnChange).toHaveBeenCalledWith(
      expect.objectContaining({ timeoutMinutes: 5 })
    )
  })

  it('resets to defaults when reset button clicked', () => {
    const customSettings = { quickMode: false, temperature: 0.8, timeoutMinutes: 5 }
    render(
      <QASettingsPopover settings={customSettings} onChange={mockOnChange} />
    )
    fireEvent.click(screen.getByRole('button', { name: /settings/i }))
    fireEvent.click(screen.getByText(/reset to defaults/i))

    expect(mockOnChange).toHaveBeenCalledWith({ ...QA_DEFAULTS })
  })
})
