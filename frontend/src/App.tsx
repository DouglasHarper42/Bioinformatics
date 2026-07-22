import { useState, useRef, useEffect, useCallback } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

interface CellEvent {
  x: number;
  y: number;
  cluster: number;
}

interface BatchResult {
  filename: string;
  columns?: string[];
  data?: CellEvent[];
  error?: string;
  totalEvents: number;
  clusterCounts: Record<number, number>;
}

const CLUSTER_METADATA = [
  { name: "Cluster 0: Lymphocytes (Blue)", color: '#3b82f6', desc: "Small, low complexity cells (T-cells, B-cells, NK cells)" },
  { name: "Cluster 1: Monocytes (Green)", color: '#10b981', desc: "Larger, moderately complex mononuclear leukocytes" },
  { name: "Cluster 2: Granulocytes (Orange)", color: '#f59e0b', desc: "High granularity and complex cellular structure (PMNs)" },
  { name: "Cluster 3: Eosinophils / Blasts", color: '#ec4899', desc: "High side scatter / hyper-granular populations" },
  { name: "Cluster 4: Debris / Platelets", color: '#8b5cf6', desc: "Low forward scatter baseline particulate matter" },
];

// Shared style for <option> elements. Note: many browsers (esp. Chromium)
// render the OPEN dropdown list using native OS styling and ignore color/background
// set on <select> alone — that's what was causing "black text on grey" in the
// dropdown popup even though the closed box looked fine. Setting colorScheme:'dark'
// on the <select> plus explicit styles on <option> fixes this reliably.
const optionStyle: React.CSSProperties = { background: '#2a2a2a', color: '#ffffff' };
const selectStyle: React.CSSProperties = {
  padding: '6px',
  background: '#333',
  color: '#fff',
  borderRadius: '4px',
  minWidth: '160px',
  colorScheme: 'dark',
};

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    return (
      <div style={{ backgroundColor: '#2a2a2a', border: '1px solid #555', padding: '12px', borderRadius: '6px', color: '#ffffff', boxShadow: '0 4px 6px rgba(0,0,0,0.3)' }}>
        <p style={{ margin: '0 0 6px 0', fontWeight: 'bold', fontSize: '14px', color: '#ffffff' }}>{`${payload[0].name} : ${Number(payload[0].value).toFixed(4)}`}</p>
        <p style={{ margin: 0, fontWeight: 'bold', fontSize: '14px', color: '#ffffff' }}>{`${payload[1].name} : ${Number(payload[1].value).toFixed(4)}`}</p>
      </div>
    );
  }
  return null;
};

// Compact color-key legend for the dots directly on the chart, per request:
// explains what the green / orange / blue dots mean without needing to read
// the full statistics panel.
const ChartLegend = ({ activeClusters }: { activeClusters: number[] }) => (
  <div style={{ display: 'flex', gap: '18px', flexWrap: 'wrap', justifyContent: 'center', marginTop: '10px' }}>
    {activeClusters.map((idx) => {
      const cluster = CLUSTER_METADATA[idx % CLUSTER_METADATA.length];
      const shortLabel = cluster.name.split(':')[1]?.split('(')[0]?.trim() || cluster.name;
      return (
        <div key={`chart-legend-${idx}`} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: cluster.color, display: 'inline-block', flexShrink: 0 }} />
          <span style={{ fontSize: '12px', color: '#ffffff', fontWeight: 500 }}>{shortLabel}</span>
        </div>
      );
    })}
  </div>
);

export default function App() {
  const [columns, setColumns] = useState<string[]>(["FSC-A", "SSC-A"]);
  const [chartKey, setChartKey] = useState(0);
  const [xIndex, setXIndex] = useState<number>(0);
  const [yIndex, setYIndex] = useState<number>(1);

  const xRef = useRef<HTMLSelectElement>(null);
  const yRef = useRef<HTMLSelectElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [clusterMode, setClusterMode] = useState<'all' | 'selected'>('all');

  // Batch upload support: multiple files can be selected at once. Each gets
  // its own entry in batchResults (success or error), and activeFileIndex
  // controls which one's data currently feeds the chart. selectedFiles is
  // kept in state (not just read once from the <input>) so that changing the
  // axis/cluster-mode selectors can re-run the SAME set of files without
  // requiring the user to re-pick them.
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [batchResults, setBatchResults] = useState<BatchResult[]>([]);
  const [activeFileIndex, setActiveFileIndex] = useState<number | null>(null);

  const activeResult = activeFileIndex !== null ? batchResults[activeFileIndex] : undefined;
  const data = activeResult?.data ?? [];

  // Uploads and clusters a single file, returning a BatchResult regardless
  // of success or failure (never throws) so the batch loop below can
  // continue processing remaining files even if one fails.
  const uploadOne = useCallback(
    async (file: File, xMarker: string, yMarker: string): Promise<BatchResult> => {
      if (!file.name.toLowerCase().endsWith('.fcs')) {
        return {
          filename: file.name,
          error: `"${file.name}" doesn't look like an .fcs file. Please choose a valid FCS file exported from your cytometer.`,
          totalEvents: 0,
          clusterCounts: {},
        };
      }

      const formData = new FormData();
      formData.append("file", file);
      formData.append("markers", `${xMarker},${yMarker}`);
      formData.append("cluster_mode", clusterMode);

      try {
        const res = await fetch("http://localhost:8000/api/cluster", {
          method: "POST",
          body: formData,
        });

        if (!res.ok) throw new Error(`Server returned status ${res.status}`);

        const json = await res.json();
        if (json.error) throw new Error(json.error);

        const resultColumns: string[] | undefined = json.columns;
        const resultData: CellEvent[] = json.columns && json.data ? json.data : json;

        const clusterCounts = resultData.reduce((acc, curr) => {
          acc[curr.cluster] = (acc[curr.cluster] || 0) + 1;
          return acc;
        }, {} as Record<number, number>);

        return {
          filename: file.name,
          columns: resultColumns,
          data: resultData,
          totalEvents: resultData.length,
          clusterCounts,
        };
      } catch (err: any) {
        console.error("Fetch error:", err);
        return {
          filename: file.name,
          error: err.message || "An unknown error occurred during clustering.",
          totalEvents: 0,
          clusterCounts: {},
        };
      }
    },
    [clusterMode]
  );

  // Processes every file in `files` against the currently selected axes and
  // clustering mode. Runs sequentially (not Promise.all) so a batch of large
  // files doesn't hammer the backend with simultaneous clustering jobs.
  const processFiles = useCallback(
    async (files: File[]) => {
      if (files.length === 0) {
        setErrorMsg("Please upload at least one .fcs file before plotting.");
        return;
      }

      setIsLoading(true);
      setErrorMsg(null);

      const xSel = xRef.current ? parseInt(xRef.current.value, 10) : xIndex;
      const ySel = yRef.current ? parseInt(yRef.current.value, 10) : yIndex;
      const xMarker = xRef.current?.options[xRef.current.selectedIndex]?.text || columns[xSel] || "FSC-A";
      const yMarker = yRef.current?.options[yRef.current.selectedIndex]?.text || columns[ySel] || "SSC-A";

      const results: BatchResult[] = [];
      for (const file of files) {
        const result = await uploadOne(file, xMarker, yMarker);
        results.push(result);
        // Update progressively so a large batch shows results as they land
        // rather than all at once at the end.
        setBatchResults([...results]);
      }

      const firstSuccessIndex = results.findIndex(r => !r.error);
      setActiveFileIndex(firstSuccessIndex !== -1 ? firstSuccessIndex : 0);

      if (firstSuccessIndex !== -1 && results[firstSuccessIndex].columns) {
        setColumns(results[firstSuccessIndex].columns!);
      }

      const allFailed = results.every(r => r.error);
      if (allFailed) {
        setErrorMsg(results.length === 1 ? results[0].error! : `All ${results.length} files failed to process. See the table below for details.`);
      } else if (results.some(r => r.error)) {
        setErrorMsg(`${results.filter(r => r.error).length} of ${results.length} file(s) failed. See the table below for details.`);
      }

      setXIndex(xSel);
      setYIndex(ySel);
      setChartKey(prev => prev + 1);
      setIsLoading(false);
    },
    [xIndex, yIndex, columns, uploadOne]
  );

  const handleFileSelection = useCallback(() => {
    const files = fileRef.current?.files ? Array.from(fileRef.current.files) : [];
    setSelectedFiles(files);
    processFiles(files);
  }, [processFiles]);

  // Re-run the current batch (if any files are selected) whenever the axis
  // or clustering mode selectors change.
  const rerunCurrentBatch = useCallback(() => {
    if (selectedFiles.length > 0) {
      processFiles(selectedFiles);
    }
  }, [selectedFiles, processFiles]);

  const currentLabelX = columns[xIndex] || "X-Axis";
  const currentLabelY = columns[yIndex] || "Y-Axis";

  const totalCells = data.length;
  const clusterCounts = data.reduce((acc, curr) => {
    acc[curr.cluster] = (acc[curr.cluster] || 0) + 1;
    return acc;
  }, {} as Record<number, number>);

  // Which clusters actually appear in the current dataset — drives the compact legend.
  const activeClusters = Object.keys(clusterCounts)
    .map(Number)
    .sort((a, b) => a - b);

  return (
    <div style={{ padding: '2rem', background: '#121212', color: '#fff', minHeight: '100vh', fontFamily: 'sans-serif' }}>
      <h1 style={{ marginBottom: '1rem', fontSize: '1.8rem', fontWeight: 'bold' }}>Clinical Cytometry Dashboard</h1>

      {/* Control Panel */}
      <div style={{ padding: '1rem', background: '#1e1e1e', borderRadius: '8px', marginBottom: '1rem', display: 'flex', gap: '15px', alignItems: 'center', flexWrap: 'wrap' }}>
        <div>
          <label htmlFor="fcs-file-input" style={{ fontSize: '12px', color: '#aaa', display: 'block', marginBottom: '4px' }}>Upload Data (.fcs, multiple allowed):</label>
          <input
            id="fcs-file-input"
            type="file"
            accept=".fcs"
            multiple
            ref={fileRef}
            onChange={handleFileSelection}
            style={{ background: '#333', color: '#fff', padding: '4px', borderRadius: '4px', colorScheme: 'dark' }}
          />
        </div>

        <div>
          <label htmlFor="x-axis-select" style={{ fontSize: '12px', color: '#aaa', display: 'block', marginBottom: '4px' }}>X-Axis Marker:</label>
          <select
            id="x-axis-select"
            ref={xRef}
            value={xIndex}
            onChange={(e) => {
              setXIndex(parseInt(e.target.value, 10));
              rerunCurrentBatch();
            }}
            style={selectStyle}
          >
            {columns.map((col, idx) => (
              <option key={`x-${idx}`} value={idx} style={optionStyle}>{col}</option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="y-axis-select" style={{ fontSize: '12px', color: '#aaa', display: 'block', marginBottom: '4px' }}>Y-Axis Marker:</label>
          <select
            id="y-axis-select"
            ref={yRef}
            value={yIndex}
            onChange={(e) => {
              setYIndex(parseInt(e.target.value, 10));
              rerunCurrentBatch();
            }}
            style={selectStyle}
          >
            {columns.map((col, idx) => (
              <option key={`y-${idx}`} value={idx} style={optionStyle}>{col}</option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="cluster-mode-select" style={{ fontSize: '12px', color: '#aaa', display: 'block', marginBottom: '4px' }}>Clustering:</label>
          <select
            id="cluster-mode-select"
            value={clusterMode}
            onChange={(e) => {
              setClusterMode(e.target.value as 'all' | 'selected');
              rerunCurrentBatch();
            }}
            style={selectStyle}
            title="'All channels' clusters using every marker in the file, so colors stay consistent as you switch axes but may look scattered on any single 2D view. 'Selected axes only' re-clusters using just the two markers currently shown, so it always looks visually clean but cluster identities change each time you switch axes."
          >
            <option value="all" style={optionStyle}>All Channels</option>
            <option value="selected" style={optionStyle}>Selected Axes Only</option>
          </select>
        </div>

        <button
          onClick={rerunCurrentBatch}
          disabled={isLoading}
          style={{
            background: isLoading ? '#555' : '#3b82f6',
            padding: '8px 20px',
            borderRadius: '4px',
            cursor: isLoading ? 'not-allowed' : 'pointer',
            fontWeight: 'bold',
            border: 'none',
            color: '#fff',
            marginTop: '16px'
          }}
        >
          {isLoading ? "Running AI..." : "Update Chart"}
        </button>
      </div>

      {errorMsg && (
        <div style={{ background: 'rgba(239, 68, 68, 0.2)', border: '1px solid #ef4444', color: '#ff8a8a', padding: '12px', borderRadius: '6px', marginBottom: '1rem' }}>
          <strong>Error:</strong> {errorMsg}
        </div>
      )}

      {batchResults.length > 1 && (
        <div style={{ background: '#1e1e1e', borderRadius: '8px', marginBottom: '1rem', overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid #333', fontSize: '13px', fontWeight: 'bold', color: '#fff' }}>
            Batch Results ({batchResults.filter(r => !r.error).length} of {batchResults.length} processed successfully) — click a row to view its chart
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
            <thead>
              <tr style={{ color: '#aaa', textAlign: 'left' }}>
                <th style={{ padding: '8px 16px' }}>File</th>
                <th style={{ padding: '8px 16px' }}>Status</th>
                <th style={{ padding: '8px 16px' }}>Events</th>
              </tr>
            </thead>
            <tbody>
              {batchResults.map((result, idx) => (
                <tr
                  key={`${result.filename}-${idx}`}
                  onClick={() => {
                    if (!result.error) {
                      setActiveFileIndex(idx);
                      if (result.columns) setColumns(result.columns);
                      setChartKey(prev => prev + 1);
                    }
                  }}
                  style={{
                    cursor: result.error ? 'default' : 'pointer',
                    background: idx === activeFileIndex ? '#2a2a2a' : 'transparent',
                    borderTop: '1px solid #2a2a2a',
                  }}
                >
                  <td style={{ padding: '8px 16px', color: '#fff' }}>{result.filename}</td>
                  <td style={{ padding: '8px 16px', color: result.error ? '#ff8a8a' : '#4ade80' }}>
                    {result.error ? `Error: ${result.error}` : 'Success'}
                  </td>
                  <td style={{ padding: '8px 16px', color: '#ccc' }}>{result.error ? '—' : result.totalEvents.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Main Layout Grid: Chart + Biological Gating Legend */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '20px', alignItems: 'start' }}>

        {/* Chart Section */}
        <div style={{ background: '#1e1e1e', padding: '20px', borderRadius: '8px', height: '540px', display: 'flex', flexDirection: 'column' }}>
          {data.length > 0 ? (
            <>
              <div style={{ flex: 1, minHeight: 0 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart key={`chart-${chartKey}`} margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                    <CartesianGrid stroke="#333" />
                    <XAxis type="number" dataKey="x" name={currentLabelX} domain={['auto', 'auto']} stroke="#888" />
                    <YAxis type="number" dataKey="y" name={currentLabelY} domain={['auto', 'auto']} stroke="#888" />

                    {/* High Contrast Custom Tooltip */}
                    <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3' }} />

                    <Scatter data={data}>
                      {data.map((entry, index) => {
                        const colorIndex = entry.cluster % CLUSTER_METADATA.length;
                        return <Cell key={`cell-${index}`} fill={CLUSTER_METADATA[colorIndex].color} />;
                      })}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
              {/* Compact dot-color legend, requested explicitly */}
              <ChartLegend activeClusters={activeClusters} />
            </>
          ) : (
            <div style={{ display: 'flex', height: '100%', justifyContent: 'center', alignItems: 'center', color: '#777', fontStyle: 'italic' }}>
              {isLoading ? "Analyzing high-dimensional matrix..." : "Upload an .fcs file and select markers to view."}
            </div>
          )}
        </div>

        {/* Biological Gating Legend & Statistics Panel */}
        <div style={{ background: '#1e1e1e', padding: '20px', borderRadius: '8px', border: '1px solid #333' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 'bold', marginBottom: '12px', borderBottom: '1px solid #333', paddingBottom: '8px', color: '#fff' }}>
            Automated Gating Legend
          </h3>
          <p style={{ fontSize: '11px', color: '#aaa', marginBottom: '14px' }}>
            Unsupervised K-Means clustering identifies distinct cellular subpopulations
            {' '}({clusterMode === 'all' ? 'based on all channels' : 'based on the two selected axes'}):
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {CLUSTER_METADATA.map((cluster, idx) => {
              const count = clusterCounts[idx] || 0;
              const percentage = totalCells > 0 ? ((count / totalCells) * 100).toFixed(1) : "0.0";

              return (
                <div key={`legend-${idx}`} style={{ background: '#252525', padding: '10px', borderRadius: '6px', borderLeft: `4px solid ${cluster.color}` }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#fff' }}>{cluster.name}</span>
                    <span style={{ fontSize: '11px', background: '#333', padding: '2px 6px', borderRadius: '4px', color: cluster.color, fontWeight: 'bold' }}>
                      {percentage}%
                    </span>
                  </div>
                  <p style={{ fontSize: '11px', color: '#999', margin: 0, lineHeight: '1.3' }}>{cluster.desc}</p>
                </div>
              );
            })}
          </div>

          <div style={{ marginTop: '16px', fontSize: '11px', color: '#777', textAlign: 'center', fontStyle: 'italic' }}>
            Total Analyzed Events: {totalCells.toLocaleString()}
          </div>
        </div>

      </div>
    </div>
  );
}
