# PKI for Agent Skills — Expansion & Future Work

## Trust Score Computation (MVP Limitations)
Currently, in Phase 2 of the MVP implementation, the `compute_author_trust` function uses hardcoded default values of `0.5` for two components of the architectural algorithm:
- **Community Reviews** (10% weight)
- **Dependency Graph Centrality** (10% weight)

This is a temporary measure because the MVP does not yet have a backend for collecting decentralized community reviews or a graph analysis tool for checking dependency bootstrapping. 

**Future Betterment Required:** 
A better way of doing this must be implemented in future phases. Specifically:
1. Integrate a review submission and aggregation API.
2. Build a DAG analysis module that computes PageRank-style centrality for the skill dependency graph.
