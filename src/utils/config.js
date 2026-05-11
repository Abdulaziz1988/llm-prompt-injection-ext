require("dotenv").config();

const config = {
  ollama: {
    host: process.env.OLLAMA_HOST || "http://127.0.0.1:11434",
    model: process.env.OLLAMA_MODEL || "llama3.2:1b",
  },
  rateLimit: {
    maxRequests: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS, 10) || 20,
    windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS, 10) || 60000,
  },
  logging: {
    file: process.env.LOG_FILE || "logs/security.log",
    verbose: process.env.LOG_VERBOSE === "true",
  },
  command: {
    timeoutMs: parseInt(process.env.COMMAND_TIMEOUT_MS, 10) || 5000,
    allowedCommands: ["ls", "date"],
  },
  chromadb: {
    host: process.env.CHROMADB_HOST || "localhost",
    port: parseInt(process.env.CHROMADB_PORT, 10) || 8000,
    enabled: process.env.CHROMADB_ENABLED !== "false",
    nResults: parseInt(process.env.CHROMADB_N_RESULTS, 10) || 5,
    distanceThreshold:
      parseFloat(process.env.CHROMADB_DISTANCE_THRESHOLD) || 1.0,
  },
  memory: {
    sessionWindow:
      parseInt(process.env.SESSION_HISTORY_WINDOW, 10) || 5,
    longTermEnabled: process.env.LONG_TERM_MEMORY_ENABLED !== "false",
    warmupEntries:
      parseInt(process.env.MEMORY_WARMUP_ENTRIES, 10) || 10,
  },
};

module.exports = config;
