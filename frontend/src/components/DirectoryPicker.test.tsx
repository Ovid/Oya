import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DirectoryPicker } from './DirectoryPicker';

describe('DirectoryPicker', () => {
  const defaultProps = {
    currentPath: '/home/user/project',
    onSwitch: vi.fn(),
    disabled: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders current path', () => {
      render(<DirectoryPicker {...defaultProps} />);
      expect(screen.getByText('/home/user/project')).toBeInTheDocument();
    });

    it('displays folder icon', () => {
      render(<DirectoryPicker {...defaultProps} />);
      // The folder icon should be present
      expect(screen.getByRole('button')).toBeInTheDocument();
    });
  });

  describe('edit mode', () => {
    it('shows input field when clicked', async () => {
      render(<DirectoryPicker {...defaultProps} />);
      
      const button = screen.getByRole('button');
      await userEvent.click(button);
      
      expect(screen.getByRole('textbox')).toBeInTheDocument();
    });

    it('input field contains current path when opened', async () => {
      render(<DirectoryPicker {...defaultProps} />);
      
      const button = screen.getByRole('button');
      await userEvent.click(button);
      
      const input = screen.getByRole('textbox');
      expect(input).toHaveValue('/home/user/project');
    });

    it('closes edit mode when Escape is pressed', async () => {
      render(<DirectoryPicker {...defaultProps} />);
      
      const button = screen.getByRole('button');
      await userEvent.click(button);
      
      await userEvent.keyboard('{Escape}');
      
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    });
  });

  describe('submit behavior', () => {
    it('calls onSwitch when Enter is pressed with new path', async () => {
      const onSwitch = vi.fn().mockResolvedValue(undefined);
      render(<DirectoryPicker {...defaultProps} onSwitch={onSwitch} />);
      
      const button = screen.getByRole('button');
      await userEvent.click(button);
      
      const input = screen.getByRole('textbox');
      await userEvent.clear(input);
      await userEvent.type(input, '/new/path{Enter}');
      
      expect(onSwitch).toHaveBeenCalledWith('/new/path');
    });

    it('calls onSwitch when submit button is clicked', async () => {
      const onSwitch = vi.fn().mockResolvedValue(undefined);
      render(<DirectoryPicker {...defaultProps} onSwitch={onSwitch} />);
      
      const button = screen.getByRole('button');
      await userEvent.click(button);
      
      const input = screen.getByRole('textbox');
      await userEvent.clear(input);
      await userEvent.type(input, '/new/path');
      
      const submitButton = screen.getByTitle('Switch workspace');
      await userEvent.click(submitButton);
      
      expect(onSwitch).toHaveBeenCalledWith('/new/path');
    });

    it('does not call onSwitch when path is unchanged', async () => {
      const onSwitch = vi.fn().mockResolvedValue(undefined);
      render(<DirectoryPicker {...defaultProps} onSwitch={onSwitch} />);
      
      const button = screen.getByRole('button');
      await userEvent.click(button);
      
      await userEvent.keyboard('{Enter}');
      
      expect(onSwitch).not.toHaveBeenCalled();
    });
  });

  describe('loading state', () => {
    it('shows loading indicator during switch', async () => {
      // Create a promise that we can control
      let resolveSwitch: () => void;
      const switchPromise = new Promise<void>((resolve) => {
        resolveSwitch = resolve;
      });
      const onSwitch = vi.fn().mockReturnValue(switchPromise);
      
      render(<DirectoryPicker {...defaultProps} onSwitch={onSwitch} />);
      
      const button = screen.getByRole('button');
      await userEvent.click(button);
      
      const input = screen.getByRole('textbox');
      await userEvent.clear(input);
      await userEvent.type(input, '/new/path{Enter}');
      
      // Should show loading state
      expect(screen.getByText('Switching...')).toBeInTheDocument();
      
      // Resolve the promise
      resolveSwitch!();
      await waitFor(() => {
        expect(screen.queryByText('Switching...')).not.toBeInTheDocument();
      });
    });

    it('disables input during loading', async () => {
      let resolveSwitch: () => void;
      const switchPromise = new Promise<void>((resolve) => {
        resolveSwitch = resolve;
      });
      const onSwitch = vi.fn().mockReturnValue(switchPromise);
      
      render(<DirectoryPicker {...defaultProps} onSwitch={onSwitch} />);
      
      const button = screen.getByRole('button');
      await userEvent.click(button);
      
      const input = screen.getByRole('textbox');
      await userEvent.clear(input);
      await userEvent.type(input, '/new/path{Enter}');
      
      // Input should be disabled during loading
      expect(screen.getByRole('textbox')).toBeDisabled();
      
      resolveSwitch!();
      await waitFor(() => {
        expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
      });
    });
  });

  describe('error handling', () => {
    it('displays error message when switch fails', async () => {
      const onSwitch = vi.fn().mockRejectedValue(new Error('Path does not exist'));
      render(<DirectoryPicker {...defaultProps} onSwitch={onSwitch} />);
      
      const button = screen.getByRole('button');
      await userEvent.click(button);
      
      const input = screen.getByRole('textbox');
      await userEvent.clear(input);
      await userEvent.type(input, '/invalid/path{Enter}');
      
      await waitFor(() => {
        expect(screen.getByText('Path does not exist')).toBeInTheDocument();
      });
    });

    it('clears error when input changes', async () => {
      const onSwitch = vi.fn().mockRejectedValue(new Error('Path does not exist'));
      render(<DirectoryPicker {...defaultProps} onSwitch={onSwitch} />);
      
      const button = screen.getByRole('button');
      await userEvent.click(button);
      
      const input = screen.getByRole('textbox');
      await userEvent.clear(input);
      await userEvent.type(input, '/invalid/path{Enter}');
      
      await waitFor(() => {
        expect(screen.getByText('Path does not exist')).toBeInTheDocument();
      });
      
      // Type something new to clear the error
      await userEvent.type(input, '/another');
      
      expect(screen.queryByText('Path does not exist')).not.toBeInTheDocument();
    });
  });

  describe('disabled state', () => {
    it('does not open edit mode when disabled', async () => {
      render(<DirectoryPicker {...defaultProps} disabled={true} />);
      
      const button = screen.getByRole('button');
      await userEvent.click(button);
      
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    });

    it('shows disabled reason when provided', () => {
      render(
        <DirectoryPicker 
          {...defaultProps} 
          disabled={true} 
          disabledReason="Cannot switch during generation" 
        />
      );
      
      expect(screen.getByTitle('Cannot switch during generation')).toBeInTheDocument();
    });

    it('applies disabled styling', () => {
      render(<DirectoryPicker {...defaultProps} disabled={true} />);
      
      const button = screen.getByRole('button');
      expect(button).toHaveClass('cursor-not-allowed');
    });
  });
});
