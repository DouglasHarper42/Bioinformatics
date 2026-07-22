// types.ts

// This interface perfectly matches the JSON dictionaries coming from your FastAPI
export interface CellEvent {
    "FSC-A": number;
    "SSC-A": number;
    cluster: number;
}

// This represents the entire array of cells you will fetch
export type ClusteredData = CellEvent[];