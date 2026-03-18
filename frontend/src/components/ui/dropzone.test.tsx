import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Dropzone } from './dropzone'

describe('ui/dropzone', () => {
  it('accepts allowed files on drop', () => {
    const onFilesAdded = vi.fn()
    render(<Dropzone onFilesAdded={onFilesAdded} accept=".pdf" />)

    const dropzone = screen.getByText(/drag & drop/i)
      .parentElement as HTMLElement
    const file = new File(['data'], 'report.pdf', { type: 'application/pdf' })

    fireEvent.drop(dropzone, { dataTransfer: { files: [file] } })

    expect(onFilesAdded).toHaveBeenCalledTimes(1)
    expect(onFilesAdded.mock.calls[0][0]).toEqual([file])
  })

  it('rejects files that do not match accept or maxSize', () => {
    const onFilesAdded = vi.fn()
    render(<Dropzone onFilesAdded={onFilesAdded} accept=".pdf" maxSize={3} />)

    const dropzone = screen.getByText(/drag & drop/i)
      .parentElement as HTMLElement
    const wrongType = new File(['hello'], 'notes.txt', { type: 'text/plain' })
    const tooLarge = new File(['large-file'], 'report.pdf', {
      type: 'application/pdf',
    })

    fireEvent.drop(dropzone, { dataTransfer: { files: [wrongType] } })
    fireEvent.drop(dropzone, { dataTransfer: { files: [tooLarge] } })

    expect(onFilesAdded).not.toHaveBeenCalled()
  })

  it('respects multiple=false and disabled state', () => {
    const onFilesAdded = vi.fn()
    const { rerender } = render(
      <Dropzone onFilesAdded={onFilesAdded} accept=".pdf" multiple={false} />
    )

    const dropzone = screen.getByText(/drag & drop/i)
      .parentElement as HTMLElement
    const fileA = new File(['a'], 'a.pdf', { type: 'application/pdf' })
    const fileB = new File(['b'], 'b.pdf', { type: 'application/pdf' })

    fireEvent.drop(dropzone, { dataTransfer: { files: [fileA, fileB] } })
    expect(onFilesAdded).toHaveBeenCalledWith([fileA])

    onFilesAdded.mockClear()
    rerender(<Dropzone onFilesAdded={onFilesAdded} disabled />)
    const disabledZone = screen.getByText(/drag & drop/i)
      .parentElement as HTMLElement

    fireEvent.drop(disabledZone, { dataTransfer: { files: [fileA] } })
    expect(onFilesAdded).not.toHaveBeenCalled()
  })

  it('does not activate drag state when disabled', () => {
    render(<Dropzone onFilesAdded={() => undefined} disabled />)

    const dropzone = screen.getByRole('button')
    fireEvent.dragOver(dropzone)
    expect(screen.getByText(/drag & drop/i)).toBeInTheDocument()
  })

  it('handles file input change', () => {
    const onFilesAdded = vi.fn()
    render(<Dropzone onFilesAdded={onFilesAdded} />)

    const input = document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement
    const file = new File(['data'], 'test.txt', { type: 'text/plain' })

    fireEvent.change(input, { target: { files: [file] } })
    expect(onFilesAdded).toHaveBeenCalledWith([file])
  })

  it('handles file input change with multiple=false', () => {
    const onFilesAdded = vi.fn()
    render(<Dropzone onFilesAdded={onFilesAdded} multiple={false} />)

    const input = document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement
    const fileA = new File(['a'], 'a.txt', { type: 'text/plain' })
    const fileB = new File(['b'], 'b.txt', { type: 'text/plain' })

    fireEvent.change(input, { target: { files: [fileA, fileB] } })
    expect(onFilesAdded).toHaveBeenCalledWith([fileA])
  })

  it('does not call onFilesAdded for empty file input', () => {
    const onFilesAdded = vi.fn()
    render(<Dropzone onFilesAdded={onFilesAdded} />)

    const input = document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement
    fireEvent.change(input, { target: { files: [] } })
    expect(onFilesAdded).not.toHaveBeenCalled()
  })

  it('accepts files matching wildcard MIME types', () => {
    const onFilesAdded = vi.fn()
    render(<Dropzone onFilesAdded={onFilesAdded} accept="image/*" />)

    const dropzone = screen.getByRole('button')
    const file = new File(['data'], 'photo.png', { type: 'image/png' })
    fireEvent.drop(dropzone, { dataTransfer: { files: [file] } })
    expect(onFilesAdded).toHaveBeenCalledWith([file])
  })

  it('opens file picker on click', () => {
    render(<Dropzone onFilesAdded={() => undefined} />)

    const input = document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement
    const clickSpy = vi.spyOn(input, 'click')

    const dropzone = screen.getByRole('button')
    fireEvent.click(dropzone)
    expect(clickSpy).toHaveBeenCalled()
  })

  it('shows drag active label and accepted hint', () => {
    render(
      <Dropzone
        onFilesAdded={() => undefined}
        accept=".pdf"
        labels={{
          idle: 'Drop files',
          active: 'Release to upload',
          accepted: 'PDF only',
        }}
      />
    )

    const dropzone = screen.getByText('Drop files').parentElement as HTMLElement
    expect(screen.getByText('PDF only')).toBeInTheDocument()

    fireEvent.dragOver(dropzone)
    expect(screen.getByText('Release to upload')).toBeInTheDocument()
  })
})
