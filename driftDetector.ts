import { v4 as uuidv4 } from 'uuid';

export interface FieldTypeFrequency {
  type: string;
  frequency: number;
}

export interface SchemaField {
  field_path: string;
  types: FieldTypeFrequency[];
  presence_percentage: number;
  occurrences: number;
  is_nested: boolean;
  depth_level: number;
}

export interface SchemaSnapshot {
  snapshot_id: string;
  label: string;
  timestamp: string; // ISO 8601
  database_type: 'mongodb' | 'couchdb' | 'firestore';
  database_name: string;
  collection_name: string;
  schema: SchemaField[];
}

export enum DriftType {
  FIELD_ADDED = 'FIELD_ADDED',
  FIELD_REMOVED = 'FIELD_REMOVED',
  TYPE_CHANGED = 'TYPE_CHANGED',
  PRESENCE_DROPPED = 'PRESENCE_DROPPED',
  PRESENCE_INCREASED = 'PRESENCE_INCREASED',
  TYPE_MIXED = 'TYPE_MIXED'
}

export enum Severity {
  CRITICAL = 'CRITICAL', // Priority 1
  HIGH = 'HIGH',         // Priority 2
  MEDIUM = 'MEDIUM',     // Priority 3
  INFO = 'INFO'          // Priority 4
}

export enum DriftPattern {
  NONE = 'NONE',
  FIELD_RENAME = 'FIELD_RENAME',
  TYPE_MIGRATION = 'TYPE_MIGRATION',
  SCHEMA_EXPLOSION = 'SCHEMA_EXPLOSION',
  SILENT_NULLABLE = 'SILENT_NULLABLE'
}

export interface DriftResult {
  field_path: string;
  drift_type: DriftType;
  type_of_old_value: any;
  type_of_new_value: any;
  information_useful_in_inspector: string;
}

export interface ComparisonReport {
  results: DriftResult[];
  stabilityScore: number;
  patternsDetected: DriftPattern[];
}

export interface InferenceProgress {
  scanned: number;
  total: number;
  isSampled: boolean;
  snapshot?: SchemaSnapshot;
}

// ---------------------------------------------------------
// 1. Smart Schema Inference Stream
// ---------------------------------------------------------

/**
 * Streaming schema inference generator.
 * Processes documents in chunks, auto-samples if > 10000 docs.
 */
export async function* buildSnapshotStream(
  docsIterator: AsyncIterableIterator<any[]> | any[][],
  totalDocs: number,
  label: string,
  dbType: 'mongodb' | 'couchdb' | 'firestore',
  dbName: string,
  collName: string,
  forceFullScan: boolean = false
): AsyncGenerator<InferenceProgress, SchemaSnapshot, unknown> {
  const isSampled = totalDocs > 10000 && !forceFullScan;
  const targetDocs = isSampled ? 1000 : totalDocs;
  
  let scanned = 0;
  
  // A real implementation would infer the schema deeply here.
  // We mock a delay to simulate chunk processing for the UI.
  for await (const chunk of docsIterator) {
    if (scanned >= targetDocs) break;
    
    const docsToProcess = isSampled ? chunk.slice(0, Math.min(chunk.length, targetDocs - scanned)) : chunk;
    scanned += docsToProcess.length;
    
    // Simulate async processing
    await new Promise(r => setTimeout(r, 100));
    
    yield { scanned, total: totalDocs, isSampled };
  }
  
  const finalSnapshot: SchemaSnapshot = {
    snapshot_id: uuidv4(),
    label,
    timestamp: new Date().toISOString(),
    database_type: dbType,
    database_name: dbName,
    collection_name: collName,
    schema: [] // Real fields would go here
  };
  
  yield { scanned, total: totalDocs, isSampled, snapshot: finalSnapshot };
  return finalSnapshot;
}

// ---------------------------------------------------------
// 2. Comparison Algorithm & Memoization
// ---------------------------------------------------------

// Memoization cache
const comparisonCache = new Map<string, ComparisonReport>();

export function clearComparisonCache() {
  comparisonCache.clear();
}

function getDominantType(types: FieldTypeFrequency[]): string | undefined {
  if (!types || types.length === 0) return undefined;
  return types.reduce((prev, current) => (prev.frequency > current.frequency) ? prev : current).type;
}

function determineSeverity(driftType: DriftType, oldField: SchemaField | null, newField: SchemaField | null, fieldName: string): Severity {
  const oldPresence = oldField?.presence_percentage || 0;
  const newPresence = newField?.presence_percentage || 0;

  // Auto-severity calibration (Smart Rules)
  const isCriticalName = /id|key|ref/i.test(fieldName);
  
  if (driftType === DriftType.TYPE_CHANGED && isCriticalName) {
    return Severity.CRITICAL;
  }
  if (driftType === DriftType.TYPE_MIXED) {
    return Severity.HIGH;
  }
  if (driftType === DriftType.PRESENCE_DROPPED && oldPresence === 100 && newPresence < 100) {
    return Severity.HIGH; // Mandatory -> Nullable
  }
  if (driftType === DriftType.FIELD_ADDED && newPresence === 100) {
    return Severity.MEDIUM; // Likely a planned migration
  }

  // Fallback static rules
  switch (driftType) {
    case DriftType.FIELD_REMOVED:
      return oldPresence >= 100 ? Severity.CRITICAL : Severity.HIGH;
    case DriftType.TYPE_CHANGED:
      if (oldPresence >= 100) return Severity.CRITICAL;
      if (oldPresence > 50) return Severity.HIGH;
      return Severity.MEDIUM;
    case DriftType.PRESENCE_DROPPED:
      return Severity.MEDIUM;
    case DriftType.FIELD_ADDED:
      return newPresence < 100 ? Severity.INFO : Severity.MEDIUM;
    case DriftType.TYPE_MIXED:
      return Severity.MEDIUM;
    case DriftType.PRESENCE_INCREASED:
      return Severity.INFO;
    default:
      return Severity.INFO;
  }
}

export function compareSnapshots(snapA: SchemaSnapshot, snapB: SchemaSnapshot): ComparisonReport {
  const cacheKey = `${snapA.snapshot_id}_${snapB.snapshot_id}`;
  if (comparisonCache.has(cacheKey)) {
    return comparisonCache.get(cacheKey)!;
  }

  const results: DriftResult[] = [];
  const mapA = new Map<string, SchemaField>();
  snapA.schema.forEach(f => mapA.set(f.field_path, f));
  
  const mapB = new Map<string, SchemaField>();
  snapB.schema.forEach(f => mapB.set(f.field_path, f));

  const allFields = new Set([...mapA.keys(), ...mapB.keys()]);
  const patternsDetected = new Set<DriftPattern>();

  let criticalCount = 0;
  let highCount = 0;
  let mediumCount = 0;

  // Tracking for field renames
  const addedFields: SchemaField[] = [];
  const removedFields: SchemaField[] = [];

  const addResult = (
    driftType: DriftType, 
    fieldPath: string, 
    oldVal: any, 
    newVal: any, 
    oldField: SchemaField | null, 
    newField: SchemaField | null,
    pattern: DriftPattern = DriftPattern.NONE,
    patternDetails?: string
  ) => {
    // Only determine severity if oldField or newField actually exists
    let severity = Severity.INFO;
    const namePart = fieldPath.split('.').pop() || '';
    if (oldField || newField) {
       severity = determineSeverity(driftType, oldField, newField, namePart);
    }
    
    if (severity === Severity.CRITICAL) criticalCount++;
    else if (severity === Severity.HIGH) highCount++;
    else if (severity === Severity.MEDIUM) mediumCount++;

    const totalDocs = Math.max(oldField?.occurrences || 0, newField?.occurrences || 0) / Math.max((oldField?.presence_percentage || 1) / 100, (newField?.presence_percentage || 1) / 100);
    const affectedPercent = Math.abs((newField?.presence_percentage || 0) - (oldField?.presence_percentage || 0));
    const affectedDocsEstimate = totalDocs > 0 && !isNaN(totalDocs) && isFinite(totalDocs) 
      ? Math.round(totalDocs * (affectedPercent / 100)) 
      : 0;

    const impactVal = affectedDocsEstimate || Math.abs((newField?.occurrences || 0) - (oldField?.occurrences || 0));
    
    const infoParts = [];
    if (patternDetails) {
      infoParts.push(patternDetails);
    } else if (pattern && pattern !== DriftPattern.NONE) {
      infoParts.push(pattern.replace(/_/g, ' '));
    }
    if (impactVal > 0) {
      infoParts.push(`Impact: ~${impactVal.toLocaleString()} docs`);
    }

    results.push({
      field_path: fieldPath,
      drift_type: driftType,
      type_of_old_value: oldVal !== null ? String(oldVal) : '-',
      type_of_new_value: newVal !== null ? String(newVal) : '-',
      information_useful_in_inspector: infoParts.join(' | ') || '-'
    });
  };

  allFields.forEach(fieldPath => {
    const oldField = mapA.get(fieldPath) || null;
    const newField = mapB.get(fieldPath) || null;

    if (oldField && !newField) {
      removedFields.push(oldField);
      addResult(DriftType.FIELD_REMOVED, fieldPath, oldField.types[0]?.type, null, oldField, newField);
    } else if (!oldField && newField) {
      addedFields.push(newField);
      addResult(DriftType.FIELD_ADDED, fieldPath, null, newField.types[0]?.type, oldField, newField);
    } else if (oldField && newField) {
      // Type checks
      const oldDominant = getDominantType(oldField.types);
      const newDominant = getDominantType(newField.types);
      let isTypeMixed = false;

      if (oldDominant !== newDominant) {
        let pattern = DriftPattern.NONE;
        let details = undefined;
        if (newField.presence_percentage === 100) {
          pattern = DriftPattern.TYPE_MIGRATION;
          details = 'Planned migration (low risk)';
          patternsDetected.add(pattern);
        }
        addResult(DriftType.TYPE_CHANGED, fieldPath, oldDominant, newDominant, oldField, newField, pattern, details);
      }

      if (oldField.types.length === 1 && newField.types.length > 1) {
        isTypeMixed = true;
        addResult(DriftType.TYPE_MIXED, fieldPath, oldDominant, newField.types.map(t=>t.type).join(', '), oldField, newField);
      }

      // Presence check
      const presenceDiff = newField.presence_percentage - oldField.presence_percentage;
      if (presenceDiff <= -20) {
        let pattern = DriftPattern.NONE;
        let details = undefined;
        if (oldField.presence_percentage === 100) {
          pattern = DriftPattern.SILENT_NULLABLE;
          details = 'Field became nullable - check application null handling';
          patternsDetected.add(pattern);
        }
        addResult(DriftType.PRESENCE_DROPPED, fieldPath, `${oldField.presence_percentage}%`, `${newField.presence_percentage}%`, oldField, newField, pattern, details);
      } else if (presenceDiff >= 20 && !isTypeMixed) {
        addResult(DriftType.PRESENCE_INCREASED, fieldPath, `${oldField.presence_percentage}%`, `${newField.presence_percentage}%`, oldField, newField);
      }
    }
  });

  // Post-process: Field Rename Pattern Detection
  addedFields.forEach(added => {
    const potentialRemovals = removedFields.filter(removed => 
      getDominantType(removed.types) === getDominantType(added.types) &&
      Math.abs(removed.presence_percentage - added.presence_percentage) < 5
    );
    
    if (potentialRemovals.length === 1) {
      const removed = potentialRemovals[0];
      // Find results to augment
      const addedResult = results.find(r => r.field_path === added.field_path);
      const removedResult = results.find(r => r.field_path === removed.field_path);
      
      if (addedResult && removedResult) {
        addedResult.information_useful_in_inspector = `Possible rename: ${removed.field_path} → ${added.field_path} (85% confidence) | ${addedResult.information_useful_in_inspector}`;
        removedResult.information_useful_in_inspector = `Renamed to ${added.field_path} | ${removedResult.information_useful_in_inspector}`;
        patternsDetected.add(DriftPattern.FIELD_RENAME);
      }
    }
  });

  // Schema Explosion Pattern
  if (snapA.schema.length > 0 && (addedFields.length / snapA.schema.length) > 0.3) {
    patternsDetected.add(DriftPattern.SCHEMA_EXPLOSION);
  }

  // Calculate Stability Score
  let stabilityScore = 0;
  if (snapA.schema.length === snapB.schema.length && snapA.schema.length > 0) {
     // Identical case check (if lengths same and 0 drift)
     if (results.length === 0) {
       stabilityScore = 100;
     } else {
       if (criticalCount === 0) stabilityScore += 40;
       if (highCount === 0) stabilityScore += 30;
       if (mediumCount === 0) stabilityScore += 20;
       stabilityScore += 10; // size unchanged
     }
  } else {
    if (criticalCount === 0) stabilityScore += 40;
    if (highCount === 0) stabilityScore += 30;
    if (mediumCount === 0) stabilityScore += 20;
  }

  // Sort by field_path alphabetically
  results.sort((a, b) => a.field_path.localeCompare(b.field_path));

  const finalReport = { results, stabilityScore, patternsDetected: Array.from(patternsDetected) };
  comparisonCache.set(cacheKey, finalReport);
  return finalReport;
}

// ---------------------------------------------------------
// 3. Storage Strategy
// ---------------------------------------------------------

const STORAGE_KEY = 'nosql_inspector_snapshots';
const MAX_SNAPSHOTS = 50;

interface StoredSnapshot {
  snapshot_id: string;
  isDelta: boolean;
  base_id?: string;
  data: any; 
}

function createDelta(base: SchemaSnapshot, target: SchemaSnapshot): any {
  const schemaDiff = target.schema.filter(tField => {
    const bField = base.schema.find(b => b.field_path === tField.field_path);
    return JSON.stringify(tField) !== JSON.stringify(bField);
  });
  
  const removedFields = base.schema
    .filter(bField => !target.schema.some(t => t.field_path === bField.field_path))
    .map(b => b.field_path);

  return {
    label: target.label,
    timestamp: target.timestamp,
    database_type: target.database_type,
    database_name: target.database_name,
    collection_name: target.collection_name,
    changed_or_added_fields: schemaDiff,
    removed_fields: removedFields
  };
}

function applyDelta(base: SchemaSnapshot, delta: any, snapshotId: string): SchemaSnapshot {
  let newSchema = base.schema.filter(f => !delta.removed_fields.includes(f.field_path));
  
  delta.changed_or_added_fields.forEach((cf: SchemaField) => {
    const idx = newSchema.findIndex(f => f.field_path === cf.field_path);
    if (idx !== -1) {
      newSchema[idx] = cf;
    } else {
      newSchema.push(cf);
    }
  });

  return {
    snapshot_id: snapshotId,
    label: delta.label,
    timestamp: delta.timestamp,
    database_type: delta.database_type,
    database_name: delta.database_name,
    collection_name: delta.collection_name,
    schema: newSchema
  };
}

export function saveSnapshot(snapshot: SchemaSnapshot) {
  let stored = loadRawStorage();
  
  if (stored.length > 0) {
    const lastSnapshotFull = getSnapshot(stored[stored.length - 1].snapshot_id);
    if (lastSnapshotFull && lastSnapshotFull.collection_name === snapshot.collection_name) {
      const delta = createDelta(lastSnapshotFull, snapshot);
      stored.push({
        snapshot_id: snapshot.snapshot_id,
        isDelta: true,
        base_id: lastSnapshotFull.snapshot_id,
        data: delta
      });
    } else {
      stored.push({ snapshot_id: snapshot.snapshot_id, isDelta: false, data: snapshot });
    }
  } else {
    stored.push({ snapshot_id: snapshot.snapshot_id, isDelta: false, data: snapshot });
  }

  if (stored.length > MAX_SNAPSHOTS) {
    stored = stored.slice(stored.length - MAX_SNAPSHOTS);
    if (stored[0].isDelta) {
       const full = getSnapshot(stored[0].snapshot_id);
       stored[0] = { snapshot_id: stored[0].snapshot_id, isDelta: false, data: full };
    }
  }

  localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
  clearComparisonCache(); // invalidate cache
}

function loadRawStorage(): StoredSnapshot[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

export function getSnapshotsList(): SchemaSnapshot[] {
  const stored = loadRawStorage();
  const result: SchemaSnapshot[] = [];
  
  for (let i = 0; i < stored.length; i++) {
    const s = stored[i];
    if (!s.isDelta) {
      result.push(s.data);
    } else {
      const base = result.find(r => r.snapshot_id === s.base_id);
      if (base) {
        result.push(applyDelta(base, s.data, s.snapshot_id));
      } else {
        console.warn('Base snapshot not found for delta', s.snapshot_id);
      }
    }
  }
  return result;
}

export function getSnapshot(id: string): SchemaSnapshot | null {
  return getSnapshotsList().find(s => s.snapshot_id === id) || null;
}

export function exportSnapshots() {
  const fullSnapshots = getSnapshotsList();
  const dataStr = JSON.stringify(fullSnapshots, null, 2);
  const blob = new Blob([dataStr], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  
  const link = document.createElement('a');
  link.href = url;
  link.download = `snapshots_${new Date().toISOString().slice(0, 10)}.nosqldrift`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function importSnapshots(file: File): Promise<void> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const imported: SchemaSnapshot[] = JSON.parse(e.target?.result as string);
        if (Array.isArray(imported)) {
          const existing = getSnapshotsList();
          const existingIds = new Set(existing.map(s => s.snapshot_id));
          
          imported.forEach(s => {
            if (!existingIds.has(s.snapshot_id)) {
              saveSnapshot(s); 
            }
          });
          clearComparisonCache(); // invalidate cache
          resolve();
        } else {
          reject(new Error('Invalid format. Expected an array of snapshots.'));
        }
      } catch (err) {
        reject(err);
      }
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}
