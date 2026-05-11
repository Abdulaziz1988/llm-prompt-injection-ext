const { getCollection } = require("./chromaClient");
const config = require("../utils/config");

/**
 * Retrieve similar security patterns from ChromaDB and format as few-shot context.
 * Returns a formatted string for prompt injection, or null if unavailable.
 */
async function retrieveSimilarPatterns(input) {
  try {
    const col = await getCollection();
    if (!col) {
      return null;
    }

    const results = await col.query({
      queryTexts: [input],
      nResults: config.chromadb.nResults,
    });

    if (!results || !results.documents || !results.documents[0]) {
      return null;
    }

    const documents = results.documents[0];
    const distances = results.distances[0];
    const metadatas = results.metadatas[0];

    // Filter by distance threshold — lower distance = more similar
    const examples = [];
    for (let i = 0; i < documents.length; i++) {
      if (distances[i] <= config.chromadb.distanceThreshold) {
        const label = metadatas[i].safe === "true" ? "SAFE" : "UNSAFE";
        const category = metadatas[i].category || "unknown";
        examples.push(`- [${label}] (${category}) "${documents[i]}"`);
      }
    }

    if (examples.length === 0) {
      return null;
    }

    return `\n\nHere are similar known patterns for reference:\n${examples.join("\n")}`;
  } catch (err) {
    console.error(`[RAGRetriever] Error: ${err.message}`);
    return null;
  }
}

module.exports = { retrieveSimilarPatterns };
