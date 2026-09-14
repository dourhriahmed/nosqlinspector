import { describe, it, expect, beforeEach } from 'vitest';
import { 
  compareSnapshots, SchemaSnapshot, DriftType, Severity, DriftPattern, clearComparisonCache
} from './driftDetector';

describe('Schema Drift Detector', () => {
  beforeEach(() => {
    clearComparisonCache();
  });

  const createBaseSnapshot = (): SchemaSnapshot => ({
    snapshot_id: '1',
    label: 'A',
    timestamp: new Date().toISOString(),
    database_type: 'mongodb',
    database_name: 'test',
    collection_name: 'users',
    schema: [
      { field_path: 'id', types: [{ type: 'string', frequency: 100 }], presence_percentage: 100, occurrences: 100, is_nested: false, depth_level: 0 },
      { field_path: 'name', types: [{ type: 'string', frequency: 100 }], presence_percentage: 100, occurrences: 100, is_nested: false, depth_level: 0 },
      { field_path: 'age', types: [{ type: 'number', frequency: 100 }], presence_percentage: 100, occurrences: 100, is_nested: false, depth_level: 0 },
    ]
  });

  it('1. Identical schemas -> empty DriftResult[]', () => {
    const snapA = createBaseSnapshot();
    const snapB = createBaseSnapshot();
    snapB.snapshot_id = '2'; // different ID to avoid cache if not cleared
    
    const report = compareSnapshots(snapA, snapB);
    expect(report.results.length).toBe(0);
    expect(report.stabilityScore).toBe(100);
  });

  it('2. One field removed -> FIELD_REMOVED, correct useful info', () => {
    const snapA = createBaseSnapshot();
    const snapB = createBaseSnapshot();
    snapB.snapshot_id = '2';
    // Remove 'name' (presence 100%)
    snapB.schema = snapB.schema.filter(f => f.field_path !== 'name');

    const report = compareSnapshots(snapA, snapB);
    expect(report.results.length).toBe(1);
    expect(report.results[0].field_path).toBe('name');
    expect(report.results[0].drift_type).toBe(DriftType.FIELD_REMOVED);
    expect(report.results[0].information_useful_in_inspector).toContain('Impact');
  });

  it('3. Type change on mandatory field -> TYPE_CHANGED', () => {
    const snapA = createBaseSnapshot();
    const snapB = createBaseSnapshot();
    snapB.snapshot_id = '2';
    // Change 'id' type (presence 100%, name 'id' makes it critical regardless, but presence 100% also makes it critical)
    const idField = snapB.schema.find(f => f.field_path === 'id')!;
    idField.types = [{ type: 'number', frequency: 100 }];

    const report = compareSnapshots(snapA, snapB);
    expect(report.results.length).toBe(1);
    expect(report.results[0].drift_type).toBe(DriftType.TYPE_CHANGED);
    expect(report.results[0].information_useful_in_inspector).toContain('Impact');
  });

  it('4. Field rename pattern detection', () => {
    const snapA = createBaseSnapshot();
    const snapB = createBaseSnapshot();
    snapB.snapshot_id = '2';
    // Rename 'name' to 'fullName'
    snapB.schema = snapB.schema.filter(f => f.field_path !== 'name');
    snapB.schema.push({
      field_path: 'fullName', 
      types: [{ type: 'string', frequency: 100 }], 
      presence_percentage: 100, 
      occurrences: 100, 
      is_nested: false, 
      depth_level: 0 
    });

    const report = compareSnapshots(snapA, snapB);
    expect(report.results.length).toBe(2); // One removal, one addition
    expect(report.patternsDetected).toContain(DriftPattern.FIELD_RENAME);
    
    const addedResult = report.results.find(r => r.drift_type === DriftType.FIELD_ADDED);
    const removedResult = report.results.find(r => r.drift_type === DriftType.FIELD_REMOVED);
    
    expect(addedResult?.information_useful_in_inspector).toContain('Possible rename');
    expect(removedResult?.information_useful_in_inspector).toContain('Renamed to');
  });

  it('5. Cross-database comparison warning trigger (Different DB Types)', () => {
    // The warning logic is in the UI, but we can verify the DB types in the snapshot structure.
    const snapA = createBaseSnapshot();
    const snapB = createBaseSnapshot();
    snapB.database_type = 'firestore';
    
    // The UI checks `snapA.database_type !== snapB.database_type`. 
    // We ensure the comparison itself runs fine without crashing.
    const report = compareSnapshots(snapA, snapB);
    expect(report.results.length).toBe(0);
    expect(snapA.database_type).not.toBe(snapB.database_type);
  });

  it('6. Stability score calculation accuracy', () => {
    const snapA = createBaseSnapshot();
    const snapB = createBaseSnapshot();
    snapB.snapshot_id = '2';
    
    // Add an optional field (INFO severity)
    snapB.schema.push({
      field_path: 'optional_notes', 
      types: [{ type: 'string', frequency: 100 }], 
      presence_percentage: 10, 
      occurrences: 10, 
      is_nested: false, 
      depth_level: 0 
    });

    const report = compareSnapshots(snapA, snapB);
    
    // Since we added a field, schema size changed (+0 to score instead of +10)
    // No CRITICAL (+40), No HIGH (+30), No MEDIUM (+20) -> Score should be 90
    expect(report.stabilityScore).toBe(90);
    
    // Let's add a medium issue (Presence Dropped)
    const snapC = createBaseSnapshot();
    snapC.snapshot_id = '3';
    const ageField = snapC.schema.find(f => f.field_path === 'age')!;
    ageField.presence_percentage = 50; // Dropped from 100 to 50
    
    const report2 = compareSnapshots(snapA, snapC);
    // age field drop from 100 to 50 triggers HIGH severity (mandatory -> nullable)
    // Score: No CRITICAL (+40), Has HIGH (+0), Has MEDIUM (+0 since HIGH is worse? Wait, No MEDIUM checks if mediumCount === 0. Actually mediumCount is 0 here).
    // Wait, `compareSnapshots` stability score: 
    // if critical == 0 (+40) -> 40
    // if high == 0 (+30) -> high is not 0 (it's 1), so +0 -> 40
    // if medium == 0 (+20) -> medium is 0, so +20 -> 60
    // length is same (+10) -> 70
    expect(report2.stabilityScore).toBe(70);
  });
});
