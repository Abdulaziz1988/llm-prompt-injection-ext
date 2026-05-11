/**
 * generateReport.js — Metrics Aggregator & Results Reporter
 *
 * Processes raw results from the ablation and/or model-comparison runs,
 * computes standard metrics, and generates both machine-readable (JSON)
 * and human-readable (Markdown) reports.
 *
 * Usage:
 *   npm run eval:report                           (reads data/results/)
 *   node scripts/generateReport.js \
 *     --input-dir data/result2                    (reads data/result2/)
 *
 * Options:
 *   --input-dir <dir>   Directory containing raw JSON files and where
 *                       report.json / report.md will be written
 *                       (default: data/results)
 *
 * Note: ablation-raw.json is optional. If absent, ablation sections are
 * omitted. model-comparison-raw.json is also optional (silently skipped).
 * At least one of the two must be present.
 */

const path = require('path');
const fs = require('fs');

// ─── CLI arg parsing ──────────────────────────────────────────────────────────

const args = process.argv.slice(2);
function getArg(name, defaultValue) {
  const idx = args.indexOf(name);
  return idx !== -1 && args[idx + 1] ? args[idx + 1] : defaultValue;
}

const RESULTS_DIR     = path.resolve(path.join(__dirname, '..', getArg('--input-dir', 'data/results')));
const ABLATION_PATH   = path.join(RESULTS_DIR, 'ablation-raw.json');
const MODEL_PATH      = path.join(RESULTS_DIR, 'model-comparison-raw.json');
const REPORT_JSON_PATH = path.join(RESULTS_DIR, 'report.json');
const REPORT_MD_PATH  = path.join(RESULTS_DIR, 'report.md');

// ─── Metric Computation ─────────────────────────────────────────────────────

function computeConfusionMatrix(results) {
  let tp = 0, fp = 0, fn = 0, tn = 0;
  for (const r of results) {
    if (r.predictedLabel === 'UNSAFE' && r.actualLabel === 'UNSAFE') tp++;
    else if (r.predictedLabel === 'UNSAFE' && r.actualLabel === 'SAFE') fp++;
    else if (r.predictedLabel === 'SAFE' && r.actualLabel === 'UNSAFE') fn++;
    else if (r.predictedLabel === 'SAFE' && r.actualLabel === 'SAFE') tn++;
  }
  return { tp, fp, fn, tn };
}

function computeMetrics(cm) {
  const { tp, fp, fn, tn } = cm;
  const total = tp + fp + fn + tn;
  const accuracy = total > 0 ? (tp + tn) / total : 0;
  const precision = (tp + fp) > 0 ? tp / (tp + fp) : 0;
  const recall = (tp + fn) > 0 ? tp / (tp + fn) : 0;
  const f1 = (precision + recall) > 0 ? (2 * precision * recall) / (precision + recall) : 0;
  const fpr = (fp + tn) > 0 ? fp / (fp + tn) : 0;
  return { accuracy, precision, recall, f1, fpr, total };
}

function computeLatencyStats(results) {
  if (results.length === 0) return { avg: 0, p50: 0, p95: 0, p99: 0 };
  const latencies = results.map((r) => r.latencyMs).sort((a, b) => a - b);
  const avg = latencies.reduce((s, l) => s + l, 0) / latencies.length;
  const p50 = latencies[Math.floor(latencies.length * 0.5)];
  const p95 = latencies[Math.floor(latencies.length * 0.95)];
  const p99 = latencies[Math.floor(latencies.length * 0.99)];
  return { avg: +avg.toFixed(1), p50, p95, p99 };
}

function pct(n) { return (n * 100).toFixed(1) + '%'; }

// ─── Ablation Analysis ──────────────────────────────────────────────────────

function analyzeAblation(data) {
  const configs = [...new Set(data.map((r) => r.config))];
  const categories = [...new Set(data.map((r) => r.category))].sort();

  const perConfig = {};
  for (const config of configs) {
    const configResults = data.filter((r) => r.config === config);
    const cm = computeConfusionMatrix(configResults);
    const metrics = computeMetrics(cm);
    const latency = computeLatencyStats(configResults);

    const perCategory = {};
    for (const cat of categories) {
      const catResults = configResults.filter((r) => r.category === cat);
      if (catResults.length === 0) continue;
      const catCm = computeConfusionMatrix(catResults);
      const catMetrics = computeMetrics(catCm);
      perCategory[cat] = { confusionMatrix: catCm, ...catMetrics, count: catResults.length };
    }

    perConfig[config] = {
      confusionMatrix: cm,
      ...metrics,
      latency,
      perCategory,
    };
  }

  // Delta analysis: how much each layer adds over the previous config
  const deltas = [];
  for (let i = 1; i < configs.length; i++) {
    const prev = perConfig[configs[i - 1]];
    const curr = perConfig[configs[i]];
    deltas.push({
      from: configs[i - 1],
      to: configs[i],
      accuracyDelta: +(curr.accuracy - prev.accuracy).toFixed(4),
      precisionDelta: +(curr.precision - prev.precision).toFixed(4),
      recallDelta: +(curr.recall - prev.recall).toFixed(4),
      f1Delta: +(curr.f1 - prev.f1).toFixed(4),
    });
  }

  return { configs, categories, perConfig, deltas };
}

// ─── Model Comparison Analysis ──────────────────────────────────────────────

function analyzeModels(data) {
  const models = [...new Set(data.map((r) => r.model))];
  const categories = [...new Set(data.map((r) => r.category))].sort();

  const perModel = {};
  for (const model of models) {
    const modelResults = data.filter((r) => r.model === model);
    const cm = computeConfusionMatrix(modelResults);
    const metrics = computeMetrics(cm);
    const latency = computeLatencyStats(modelResults);

    const perCategory = {};
    for (const cat of categories) {
      const catResults = modelResults.filter((r) => r.category === cat);
      if (catResults.length === 0) continue;
      const catCm = computeConfusionMatrix(catResults);
      const catMetrics = computeMetrics(catCm);
      perCategory[cat] = { confusionMatrix: catCm, ...catMetrics, count: catResults.length };
    }

    perModel[model] = {
      confusionMatrix: cm,
      ...metrics,
      latency,
      perCategory,
    };
  }

  return { models, categories, perModel };
}

// ─── False Positive Analysis ────────────────────────────────────────────────

function analyzeFalsePositives(data, groupKey) {
  const groups = [...new Set(data.map((r) => r[groupKey]))];
  const result = {};

  for (const group of groups) {
    const fps = data.filter(
      (r) => r[groupKey] === group && r.predictedLabel === 'UNSAFE' && r.actualLabel === 'SAFE'
    );

    const bySubcategory = {};
    for (const fp of fps) {
      const key = `${fp.category}/${fp.subcategory}`;
      if (!bySubcategory[key]) {
        bySubcategory[key] = { count: 0, examples: [] };
      }
      bySubcategory[key].count++;
      if (bySubcategory[key].examples.length < 3) {
        bySubcategory[key].examples.push(fp.input);
      }
    }

    result[group] = { totalFP: fps.length, bySubcategory };
  }

  return result;
}

// ─── Markdown Report ────────────────────────────────────────────────────────

function generateMarkdown(ablation, models, ablationFalsePositives, modelFalsePositives) {
  const lines = [];
  const h = (level, text) => lines.push(`${'#'.repeat(level)} ${text}\n`);
  const p = (text) => lines.push(`${text}\n`);

  h(1, 'Evaluation Results Report');
  p(`Generated: ${new Date().toISOString()}`);

  if (ablation) {
    // ── Table 1: Ablation Confusion Matrices ──
    h(2, 'Table 1: Ablation Confusion Matrices');
    lines.push('| Configuration | TP | FP | FN | TN | Total |');
    lines.push('|---|---|---|---|---|---|');
    for (const config of ablation.configs) {
      const c = ablation.perConfig[config].confusionMatrix;
      lines.push(`| ${config} | ${c.tp} | ${c.fp} | ${c.fn} | ${c.tn} | ${c.tp + c.fp + c.fn + c.tn} |`);
    }
    lines.push('');

    // ── Table 2: Per-Configuration Metrics ──
    h(2, 'Table 2: Per-Configuration Precision / Recall / F1');
    lines.push('| Configuration | Accuracy | Precision | Recall | F1 | FPR | Avg Latency | P95 Latency |');
    lines.push('|---|---|---|---|---|---|---|---|');
    for (const config of ablation.configs) {
      const m = ablation.perConfig[config];
      lines.push(
        `| ${config} | ${pct(m.accuracy)} | ${pct(m.precision)} | ${pct(m.recall)} | ${pct(m.f1)} | ${pct(m.fpr)} | ${m.latency.avg}ms | ${m.latency.p95}ms |`
      );
    }
    lines.push('');

    // ── Table 3: Per-Category F1 Across Configurations ──
    h(2, 'Table 3: Per-Category F1 Across Configurations');
    const catHeader = ['Category', ...ablation.configs];
    lines.push(`| ${catHeader.join(' | ')} |`);
    lines.push(`|${catHeader.map(() => '---').join('|')}|`);
    for (const cat of ablation.categories) {
      const row = [cat];
      for (const config of ablation.configs) {
        const catData = ablation.perConfig[config].perCategory[cat];
        row.push(catData ? pct(catData.f1) : 'N/A');
      }
      lines.push(`| ${row.join(' | ')} |`);
    }
    lines.push('');

    // ── Table 4: Layer Delta Analysis ──
    h(2, 'Table 4: Layer Contribution (Delta Analysis)');
    lines.push('| Added Layer(s) | Accuracy Delta | Precision Delta | Recall Delta | F1 Delta |');
    lines.push('|---|---|---|---|---|');
    for (const d of ablation.deltas) {
      const sign = (n) => (n >= 0 ? '+' : '') + pct(n);
      lines.push(
        `| ${d.from} → ${d.to} | ${sign(d.accuracyDelta)} | ${sign(d.precisionDelta)} | ${sign(d.recallDelta)} | ${sign(d.f1Delta)} |`
      );
    }
    lines.push('');
  }

  // ── Model Comparison Tables ──
  if (models) {
    let tNum = ablation ? 5 : 1;

    // Model metrics summary
    h(2, `Table ${tNum}: Model Size vs. Accuracy vs. Latency`);
    lines.push('| Model | Accuracy | Precision | Recall | F1 | FPR | Avg Latency | P95 Latency |');
    lines.push('|---|---|---|---|---|---|---|---|');
    for (const model of models.models) {
      const m = models.perModel[model];
      lines.push(
        `| ${model} | ${pct(m.accuracy)} | ${pct(m.precision)} | ${pct(m.recall)} | ${pct(m.f1)} | ${pct(m.fpr)} | ${m.latency.avg}ms | ${m.latency.p95}ms |`
      );
    }
    lines.push('');
    tNum++;

    // Model confusion matrices
    h(2, `Table ${tNum}: Per-Model Confusion Matrices`);
    lines.push('| Model | TP | FP | FN | TN | Total |');
    lines.push('|---|---|---|---|---|---|');
    for (const model of models.models) {
      const c = models.perModel[model].confusionMatrix;
      lines.push(`| ${model} | ${c.tp} | ${c.fp} | ${c.fn} | ${c.tn} | ${c.tp + c.fp + c.fn + c.tn} |`);
    }
    lines.push('');
    tNum++;

    // Per-category F1 across models
    h(2, `Table ${tNum}: Per-Category F1 Across Models`);
    const mCatHeader = ['Category', ...models.models];
    lines.push(`| ${mCatHeader.join(' | ')} |`);
    lines.push(`|${mCatHeader.map(() => '---').join('|')}|`);
    for (const cat of models.categories) {
      const row = [cat];
      for (const model of models.models) {
        const catData = models.perModel[model].perCategory[cat];
        row.push(catData ? pct(catData.f1) : 'N/A');
      }
      lines.push(`| ${row.join(' | ')} |`);
    }
    lines.push('');
    tNum++;

    // Per-category accuracy across models
    h(2, `Table ${tNum}: Per-Category Accuracy Across Models`);
    const mAccHeader = ['Category', ...models.models];
    lines.push(`| ${mAccHeader.join(' | ')} |`);
    lines.push(`|${mAccHeader.map(() => '---').join('|')}|`);
    for (const cat of models.categories) {
      const row = [cat];
      for (const model of models.models) {
        const catData = models.perModel[model].perCategory[cat];
        row.push(catData ? pct(catData.accuracy) : 'N/A');
      }
      lines.push(`| ${row.join(' | ')} |`);
    }
    lines.push('');
    tNum++;

    // Latency breakdown
    h(2, `Table ${tNum}: Latency Breakdown by Model`);
    lines.push('| Model | Avg (ms) | P50 (ms) | P95 (ms) | P99 (ms) |');
    lines.push('|---|---|---|---|---|');
    for (const model of models.models) {
      const l = models.perModel[model].latency;
      lines.push(`| ${model} | ${l.avg} | ${l.p50} | ${l.p95} | ${l.p99} |`);
    }
    lines.push('');
    tNum++;

    // False positive analysis for models
    if (modelFalsePositives) {
      h(2, `Table ${tNum}: False Positive Analysis by Model`);
      lines.push('| Model | Total FP | Top False Positive Sources |');
      lines.push('|---|---|---|');
      for (const model of models.models) {
        const fp = modelFalsePositives[model];
        const topSources = Object.entries(fp.bySubcategory)
          .sort((a, b) => b[1].count - a[1].count)
          .slice(0, 3)
          .map(([key, v]) => `${key} (${v.count})`)
          .join(', ');
        lines.push(`| ${model} | ${fp.totalFP} | ${topSources || 'none'} |`);
      }
      lines.push('');
      tNum++;
    }
  }

  // ── Ablation False Positive Analysis ──
  if (ablation && ablationFalsePositives) {
    h(2, 'Table 6: False Positive Analysis');
    lines.push('| Configuration | Total FP | Top False Positive Sources |');
    lines.push('|---|---|---|');
    for (const config of ablation.configs) {
      const fp = ablationFalsePositives[config];
      const topSources = Object.entries(fp.bySubcategory)
        .sort((a, b) => b[1].count - a[1].count)
        .slice(0, 3)
        .map(([key, v]) => `${key} (${v.count})`)
        .join(', ');
      lines.push(`| ${config} | ${fp.totalFP} | ${topSources || 'none'} |`);
    }
    lines.push('');
  }

  return lines.join('\n');
}

// ─── Main ────────────────────────────────────────────────────────────────────

function main() {
  console.log('\n  Metrics Aggregator & Report Generator');
  console.log('  ─────────────────────────────────────');
  console.log(`  Input dir: ${path.relative(process.cwd(), RESULTS_DIR)}`);

  // Load ablation results (optional)
  let ablationData = null;
  if (fs.existsSync(ABLATION_PATH)) {
    ablationData = JSON.parse(fs.readFileSync(ABLATION_PATH, 'utf-8'));
    console.log(`  Ablation results: ${ablationData.length} entries`);
  } else {
    console.log('  Ablation results: not found (skipping ablation sections)');
  }

  // Load model comparison results (optional)
  let modelData = null;
  if (fs.existsSync(MODEL_PATH)) {
    modelData = JSON.parse(fs.readFileSync(MODEL_PATH, 'utf-8'));
    console.log(`  Model comparison results: ${modelData.length} entries`);
  } else {
    console.log('  Model comparison results: not found (skipping)');
  }

  if (!ablationData && !modelData) {
    console.error('  No result files found. Run at least one evaluation first.');
    process.exit(1);
  }

  // Analyze
  const ablation = ablationData ? analyzeAblation(ablationData) : null;
  const models = modelData ? analyzeModels(modelData) : null;
  const ablationFalsePositives = ablationData ? analyzeFalsePositives(ablationData, 'config') : null;
  const modelFalsePositives = modelData ? analyzeFalsePositives(modelData, 'model') : null;

  // Ensure output directory exists
  if (!fs.existsSync(RESULTS_DIR)) {
    fs.mkdirSync(RESULTS_DIR, { recursive: true });
  }

  // Build report object
  const report = {
    generatedAt: new Date().toISOString(),
    ablation,
    models,
    ablationFalsePositives,
    modelFalsePositives,
  };

  // Write JSON report
  fs.writeFileSync(REPORT_JSON_PATH, JSON.stringify(report, null, 2));
  console.log(`  JSON report: ${path.relative(process.cwd(), REPORT_JSON_PATH)}`);

  // Write Markdown report
  const markdown = generateMarkdown(ablation, models, ablationFalsePositives, modelFalsePositives);
  fs.writeFileSync(REPORT_MD_PATH, markdown);
  console.log(`  Markdown report: ${path.relative(process.cwd(), REPORT_MD_PATH)}`);

  // Print quick summary
  if (ablation) {
    console.log('\n  Quick Summary (Ablation):');
    for (const config of ablation.configs) {
      const m = ablation.perConfig[config];
      console.log(`    ${config.padEnd(35)} F1=${pct(m.f1).padEnd(7)} Acc=${pct(m.accuracy)}`);
    }
  }

  if (models) {
    console.log('\n  Quick Summary (Model Comparison):');
    for (const model of models.models) {
      const m = models.perModel[model];
      console.log(`    ${model.padEnd(20)} F1=${pct(m.f1).padEnd(7)} Acc=${pct(m.accuracy).padEnd(7)} AvgLat=${m.latency.avg}ms`);
    }
  }

  console.log('');
}

main();
