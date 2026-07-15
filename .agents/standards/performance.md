# performance.md — Performance Principles for NewsIQ

This standard outlines the general engineering principles for ensuring high performance and resource efficiency across services.

## 1. Latency Optimization Principles
- **Asynchronous Execution**: Perform I/O operations asynchronously to prevent thread blocking.
- **Payload Management**: Keep JSON responses and data payloads as small as possible; avoid retrieving fields that are not consumed by the caller.
- **Cache-First Designs**: Query cache layers (such as Redis or semantic search caches) for highly requested data before hitting primary database storage.

## 2. Database Query Efficiency
- **N+1 Prevention**: Structure database queries to pull related associations in batches (using eager loading or joint queries).
- **Indexing Alignment**: Ensure queries target indexes to avoid expensive database table scans.

## 3. Resource & Memory Auditing
- **Leak Prevention**: Close database connections, client sessions, and file descriptors immediately after use.
- **Batch Processing**: Use cursors or stream pagination when processing large datasets to prevent RAM exhaustion.
