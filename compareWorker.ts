import { compareSnapshots, SchemaSnapshot, ComparisonReport } from './driftDetector';

self.onmessage = (e: MessageEvent<{ snapA: SchemaSnapshot; snapB: SchemaSnapshot }>) => {
  const { snapA, snapB } = e.data;
  
  try {
    // Run the heavy comparison
    const report: ComparisonReport = compareSnapshots(snapA, snapB);
    
    // Post back the result
    self.postMessage({ type: 'SUCCESS', report });
  } catch (error: any) {
    self.postMessage({ type: 'ERROR', error: error.message });
  }
};
