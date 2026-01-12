import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DirectoryPicker } from './DirectoryPicker';
import * as api from '../api/client';

// Mock the API module
vi.mock('../api/client', () => ({
  listDirectories: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
}));

describe('DirectoryPicker', () => {
  const defaultProps = {
    currentPath: '/home/user/project',
    isDocker: false,
    onSwitch: vi.fn(),
    disabled: false,
  };

  const mockDirectoryListing = {
    path: '/home/user',
    parent: '/home',
    entries: [
      { name: 'project', path: '/home/user/project', is_dir: true },
      { name: 'documents', path: '/home/user/documents', is_dir: true },
      { name: 'file.txt', path: '/home/user/file.txt', is_dir: false },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listDirectories).mockResolvedValue(mockDirectoryListing);
  });

  describe('rendering', () => {
    it('renders current path', () => {
      render(<DirectoryPicker {...defaultProps} />);
      expect(screen.getByText('/home/user/project')).toBeInTheDocument();
    });

    it('displays folder icon', () => {
      render(<DirectoryPicker {...defaultProps} />);
      expect(screen.getByRole('button')).toBeInTheDocument();
    });
  });

  describe('modal behavior', () => {
    it('opens modal when clicked', async () => {
      render(<DirectoryPicker {...defaultProps} />);
      
      const button = screen.getByRole('button');
      await userEvent.click(button);
      
      expect(screen.getByText('Select Workspace')).toBeInTheDocument();
    });

    it('closes modal when Cancel is clicked', async () => {
      render(<DirectoryPicker {...defaultProps} />);
      
      await userEvent.click(screen.getByRole('button'));
      await waitFor(() => {
        expect(screen.getByText('Select Workspace')).toBeInTheDocument();
      });
      
      await userEvent.click(screen.getByText('Cancel'));
      
      expect(screen.queryByText('Select Workspace')).not.toBeInTheDocument();
    });

    it('closes modal when X button is clicked', async () => {
      render(<DirectoryPicker {...defaultProps} />);
      
      await userEvent.click(screen.getByRole('button'));
      await waitFor(() => {
        expect(screen.getByText('Select Workspace')).toBeInTheDocument();
      });
      
      await userEvent.click(screen.getByLabelText('Close'));
      
      expect(screen.queryByText('Select Workspace')).not.toBeInTheDocument();
    });
  });

  describe('directory browsing', () => {
    it('loads directories when modal opens', async () => {
      render(<DirectoryPicker {...defaultProps} />);
      
      await userEvent.click(screen.getByRole('button'));
      
      await waitFor(() => {
        expect(api.listDirectories).toHaveBeenCalled();
      });
    });

    it('displays directory entries', async () => {
      render(<DirectoryPicker {...defaultProps} />);
      
      await userEvent.click(screen.getByRole('button'));
      
      await waitFor(() => {
        expect(screen.getByText('project')).toBeInTheDocument();
        expect(screen.getByText('documents')).toBeInTheDocument();
      });
    });

    it('only shows directories, not files', async () => {
      render(<DirectoryPicker {...defaultProps} />);
      
      await userEvent.click(screen.getByRole('button'));
      
      await waitFor(() => {
        expect(screen.getByText('project')).toBeInTheDocument();
      });
      
      // file.txt should not be shown
      expect(screen.queryByText('file.txt')).not.toBeInTheDocument();
    });

    it('navigates to subdirectory when clicked', async () => {
      render(<DirectoryPicker {...defaultProps} />);
      
      await userEvent.click(screen.getByRole('button'));
      
      await waitFor(() => {
        expect(screen.getByText('project')).toBeInTheDocument();
      });
      
      await userEvent.click(screen.getByText('project'));
      
      expect(api.listDirectories).toHaveBeenCalledWith('/home/user/project');
    });

    it('shows parent directory navigation', async () => {
      render(<DirectoryPicker {...defaultProps} />);
      
      await userEvent.click(screen.getByRole('button'));
      
      await waitFor(() => {
        expect(screen.getByText('..')).toBeInTheDocument();
      });
    });
  });

  describe('workspace selection', () => {
    it('calls onSwitch when Select is clicked', async () => {
      const onSwitch = vi.fn().mockResolvedValue(undefined);
      render(<DirectoryPicker {...defaultProps} onSwitch={onSwitch} />);
      
      await userEvent.click(screen.getByRole('button'));
      
      await waitFor(() => {
        expect(screen.getByText('Select')).toBeInTheDocument();
      });
      
      await userEvent.click(screen.getByText('Select'));
      
      expect(onSwitch).toHaveBeenCalledWith('/home/user');
    });

    it('closes modal after successful switch', async () => {
      const onSwitch = vi.fn().mockResolvedValue(undefined);
      render(<DirectoryPicker {...defaultProps} onSwitch={onSwitch} />);
      
      await userEvent.click(screen.getByRole('button'));
      
      await waitFor(() => {
        expect(screen.getByText('Select')).toBeInTheDocument();
      });
      
      await userEvent.click(screen.getByText('Select'));
      
      await waitFor(() => {
        expect(screen.queryByText('Select Workspace')).not.toBeInTheDocument();
      });
    });
  });

  describe('error handling', () => {
    it('displays error when directory listing fails', async () => {
      vi.mocked(api.listDirectories).mockRejectedValue(new Error('Permission denied'));
      
      render(<DirectoryPicker {...defaultProps} />);
      
      await userEvent.click(screen.getByRole('button'));
      
      await waitFor(() => {
        // The component shows a generic message when the error isn't an ApiError
        expect(screen.getByText(/Failed to load directories/)).toBeInTheDocument();
      });
    });

    it('displays error when switch fails', async () => {
      const onSwitch = vi.fn().mockRejectedValue(new Error('Path does not exist'));
      render(<DirectoryPicker {...defaultProps} onSwitch={onSwitch} />);
      
      await userEvent.click(screen.getByRole('button'));
      
      await waitFor(() => {
        expect(screen.getByText('Select')).toBeInTheDocument();
      });
      
      await userEvent.click(screen.getByText('Select'));
      
      await waitFor(() => {
        expect(screen.getByText(/Path does not exist/)).toBeInTheDocument();
      });
    });

    it('shows Docker note in error when in Docker mode', async () => {
      const onSwitch = vi.fn().mockRejectedValue(new Error('Path does not exist'));
      render(<DirectoryPicker {...defaultProps} isDocker={true} onSwitch={onSwitch} />);
      
      await userEvent.click(screen.getByRole('button'));
      
      await waitFor(() => {
        expect(screen.getByText('Select')).toBeInTheDocument();
      });
      
      await userEvent.click(screen.getByText('Select'));
      
      await waitFor(() => {
        expect(screen.getByText(/Docker mode/)).toBeInTheDocument();
      });
    });
  });

  describe('Docker mode', () => {
    it('shows Docker indicator when in Docker mode', async () => {
      render(<DirectoryPicker {...defaultProps} isDocker={true} />);
      
      await userEvent.click(screen.getByRole('button'));
      
      await waitFor(() => {
        expect(screen.getByText('Running in Docker')).toBeInTheDocument();
      });
    });

    it('does not show Docker indicator when not in Docker mode', async () => {
      render(<DirectoryPicker {...defaultProps} isDocker={false} />);
      
      await userEvent.click(screen.getByRole('button'));
      
      await waitFor(() => {
        expect(screen.getByText('Select Workspace')).toBeInTheDocument();
      });
      
      expect(screen.queryByText('Running in Docker')).not.toBeInTheDocument();
    });
  });

  describe('disabled state', () => {
    it('does not open modal when disabled', async () => {
      render(<DirectoryPicker {...defaultProps} disabled={true} />);
      
      const button = screen.getByRole('button');
      await userEvent.click(button);
      
      expect(screen.queryByText('Select Workspace')).not.toBeInTheDocument();
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
