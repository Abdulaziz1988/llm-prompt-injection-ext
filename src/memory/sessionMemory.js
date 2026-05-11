const config = require("../utils/config");

const WINDOW = config.memory.sessionWindow;

// Each entry: { input, status, violationType, ts }
let history = [];

/**
 * Record the outcome of a processed turn.
 */
function record(input, status, violationType) {
  history.push({
    input: input.substring(0, 200),
    status,
    violationType,
    ts: Date.now(),
  });
  if (history.length > WINDOW) {
    history = history.slice(-WINDOW);
  }
}

/**
 * Return a copy of the current window (oldest first).
 */
function getHistory() {
  return [...history];
}

/**
 * Detect multi-turn escalation patterns in the history.
 * Returns { escalating: bool, reason: string|null }.
 *
 * Patterns:
 * 1. 2+ violations in window → persistent attacker
 * 2. Safe turns followed by a violation → reconnaissance then attack
 */
function detectEscalation() {
  if (history.length < 2) {
    return { escalating: false, reason: null };
  }

  const violations = history.filter((h) => h.status === "VIOLATION");
  if (violations.length >= 2) {
    return {
      escalating: true,
      reason: `Multi-turn attack: ${violations.length} violations in last ${history.length} turns`,
    };
  }

  const last = history[history.length - 1];
  if (
    last?.status === "VIOLATION" &&
    history.slice(0, -1).every((h) => h.status === "SAFE")
  ) {
    return {
      escalating: true,
      reason:
        "Escalation pattern: safe reconnaissance turns followed by attack",
    };
  }

  return { escalating: false, reason: null };
}

/**
 * Format history as a compact context block for the semantic validator prompt.
 * Returns a string or null if history is empty.
 */
function formatContextBlock() {
  if (history.length === 0) {
    return null;
  }

  const lines = history.map((h, i) => {
    const snippet = h.input.replace(/\n/g, " ").substring(0, 80);
    const label =
      h.status === "VIOLATION"
        ? `VIOLATION[${h.violationType}]`
        : "SAFE";
    return `Turn ${i + 1}: "${snippet}" → ${label}`;
  });

  return `\n\nConversation history (${history.length} prior turns):\n${lines.join("\n")}`;
}

/**
 * Reset history — used for test isolation.
 */
function reset() {
  history = [];
}

module.exports = { record, getHistory, detectEscalation, formatContextBlock, reset };
