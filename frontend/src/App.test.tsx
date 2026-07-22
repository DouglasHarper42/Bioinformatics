import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';

// Recharts' ResponsiveContainer needs real layout dimensions to render its
// children, which jsdom doesn't provide. Mocking getBoundingClientRect keeps
// the chart from silently rendering empty in the test environment.
beforeEach(() => {
  Element.prototype.getBoundingClientRect = () => ({
    width: 800,
    height: 400,
    top: 0,
    left: 0,
    bottom: 0,
    right: 0,
    x: 0,
    y: 0,
    toJSON: () => {},
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function makeFile(name: string, content = 'fake bytes') {
  return new File([content], name, { type: 'application/octet-stream' });
}

// userEvent.upload() respects the input's accept=".fcs" attribute and will
// silently refuse to attach a non-matching file — accurately mimicking a
// real OS file picker restricted to that type. But real users CAN still
// select a non-matching file (e.g. choosing "All Files" in the dialog),
// which is exactly the scenario our client-side validation guards against.
// fireEvent bypasses that picker-level filtering so we can actually test
// what the app does when a mismatched file gets through.
function uploadFileBypassingAcceptFilter(input: HTMLInputElement, file: File) {
  Object.defineProperty(input, 'files', {
    value: [file],
    writable: true,
    configurable: true,
  });
  act(() => {
    fireEvent.change(input);
  });
}

describe('App - file type validation', () => {
  it('shows a clear error banner and does NOT call fetch when a non-.fcs file is uploaded', async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);

    render(<App />);
    const fileInput = screen.getByLabelText(/upload data/i) as HTMLInputElement;
    uploadFileBypassingAcceptFilter(fileInput, makeFile('results.csv'));

    // Error banner should appear, naming the offending file
    expect(await screen.findByText(/error/i)).toBeInTheDocument();
    expect(screen.getByText(/results\.csv/)).toBeInTheDocument();
    expect(screen.getByText(/doesn't look like an \.fcs file/i)).toBeInTheDocument();

    // Client-side validation should reject BEFORE ever hitting the network
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('does not show a blank/broken state after an invalid upload — the "upload a file" placeholder remains visible', async () => {
    vi.stubGlobal('fetch', vi.fn());

    render(<App />);
    const fileInput = screen.getByLabelText(/upload data/i) as HTMLInputElement;
    uploadFileBypassingAcceptFilter(fileInput, makeFile('notes.txt'));

    await screen.findByText(/error/i);
    // The chart panel should still show its normal empty-state prompt,
    // not a silently blank panel.
    expect(screen.getByText(/upload an \.fcs file and select markers to view/i)).toBeInTheDocument();
  });
});

describe('App - successful upload flow', () => {
  it('renders the legend and clears any previous error after a successful upload', async () => {
    const mockResponse = {
      columns: ['FSC-A', 'SSC-A', 'FL1-A'],
      cluster_mode: 'all',
      data: [
        { x: 1.2, y: 3.4, cluster: 0 },
        { x: 2.1, y: 1.9, cluster: 1 },
        { x: 0.5, y: 4.4, cluster: 2 },
      ],
    };

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      })
    );

    render(<App />);
    const user = userEvent.setup();

    const fileInput = screen.getByLabelText(/upload data/i) as HTMLInputElement;
    await user.upload(fileInput, makeFile('sample.fcs'));

    await waitFor(() => {
      expect(screen.getByText(/automated gating legend/i)).toBeInTheDocument();
    });

    // No error banner should be present after a successful response
    expect(screen.queryByText(/^error:/i)).not.toBeInTheDocument();

    // Total analyzed events should reflect the mocked data length
    expect(screen.getByText(/total analyzed events: 3/i)).toBeInTheDocument();
  });

  it('shows a red error banner and keeps Total Analyzed Events at 0 when the backend returns an error payload', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ error: 'This file could not be read as a valid FCS file.' }),
      })
    );

    render(<App />);
    const user = userEvent.setup();

    const fileInput = screen.getByLabelText(/upload data/i) as HTMLInputElement;
    await user.upload(fileInput, makeFile('corrupted.fcs'));

    expect(await screen.findByText(/could not be read as a valid fcs file/i)).toBeInTheDocument();
    // The stats/legend panel is always rendered (by design), but on an
    // error it should show 0 analyzed events rather than stale/fake data.
    expect(screen.getByText(/total analyzed events: 0/i)).toBeInTheDocument();
    // And the chart area itself should show the empty-state prompt, not
    // a chart rendered from nonexistent data.
    expect(screen.getByText(/upload an \.fcs file and select markers to view/i)).toBeInTheDocument();
  });
});
