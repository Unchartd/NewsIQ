# Event Identity Architecture

This document describes the identity management lifecycle for NewsIQ stories, ensuring a stable, immutable identifier system capable of gracefully handling the messy, noisy reality of breaking news clustering.

## 1. Core Principles

- **Separation of Identity & Display**: The underlying `canonical_event_id` is an immutable, opaque identifier (`evt_<base32>`). The human-readable slug (`apple-ai-chip-launch-2026`) is treated purely as mutable display metadata.
- **Gradual Maturation**: Events start with temporary UUIDs (`tmp_evt_<uuid>`) during discovery and clustering. They only receive a Canonical ID when they mature (transition to `MONITORING` or `STABLE`).
- **History Preservation**: When two canonical events merge, the deprecated ID is preserved as an `EventAlias` pointing to the surviving ID, ensuring external links and historical references never break.

---

## 2. Sequence Diagrams

### 2.1. Initial Discovery & Temporary ID Assignment
When a new cluster forms, it receives a temporary ID.

```mermaid
sequenceDiagram
    participant I as Ingestion Pipeline
    participant C as ClusteringService
    participant E as EventIdentityService
    participant DB as Database
    
    I->>C: Submit unclustered articles
    C->>C: HDBSCAN identifies new cluster
    C->>E: generate_temporary_id()
    E-->>C: Returns tmp_evt_<uuid>
    C->>DB: Save new Story with tmp_evt_<uuid>
```

### 2.2. Lifecycle Graduation & Canonical ID Assignment
As more articles join the cluster and its confidence grows, the LifecycleManager promotes it.

```mermaid
sequenceDiagram
    participant C as ClusteringService (Incremental Merge)
    participant L as LifecycleManager
    participant E as EventIdentityService
    participant DB as Database
    
    C->>L: evaluate_and_transition(story)
    L->>L: Rules Engine calculates health > threshold
    L->>L: Determine transition to MONITORING
    
    opt If story has no Canonical ID (starts with tmp_evt_)
        L->>E: generate_canonical_id()
        E-->>L: Returns evt_<base32>
        L->>E: generate_display_slug(headline)
        E-->>L: Returns human-readable slug
        L->>DB: Update Story with canonical IDs
    end
    
    L->>DB: Update Story state to MONITORING
```

### 2.3. Story Merging & Alias Creation
When two mature stories are found to be identical and are merged.

```mermaid
sequenceDiagram
    participant C as ClusteringService (Merge Task)
    participant E as EventIdentityService
    participant DB as Database
    
    C->>C: Detect Story A and Story B are identical
    C->>C: Decide Story B is canonical (higher confidence/older)
    C->>DB: Merge articles and metadata to Story B
    
    C->>E: handle_merge(old_id=A.canonical, new_id=B.canonical)
    E->>DB: Create EventAlias (alias=A.canonical, canonical=B.canonical)
    
    C->>DB: Delete/Archive Story A
```

### 2.4. Alias Resolution
When the API receives a request for an ID that might have been merged.

```mermaid
sequenceDiagram
    participant API as API Route
    participant E as EventIdentityService
    participant DB as Database
    
    API->>DB: Fetch Story by ID
    alt Story Found
        DB-->>API: Return Story
    else Story Not Found
        API->>E: resolve_alias(requested_id)
        E->>DB: Query EventAlias table iteratively
        DB-->>E: Return final canonical ID
        E-->>API: Return canonical ID
        API->>DB: Fetch Story by canonical ID
        DB-->>API: Return Story (or 404)
    end
```

### 2.5. Lifecycle State Transitions
This state diagram illustrates the progression of a Story through its lifecycle states, and where the Canonical ID gets assigned.

```mermaid
stateDiagram-v2
    [*] --> PENDING: Initial discovery
    
    PENDING --> DEVELOPING: Cluster formed
    note right of DEVELOPING
      Assigned: tmp_evt_<uuid>
    end note
    
    DEVELOPING --> MONITORING: Meets health & confidence criteria
    note right of MONITORING
      Assigned: evt_<base32>
      (Canonical Event ID)
    end note
    
    MONITORING --> STABLE: Cluster stabilized, no new sources
    
    STABLE --> DEVELOPING: Significant new information
    
    MONITORING --> ARCHIVED: Deprecated/Merged
    STABLE --> ARCHIVED: Deprecated/Merged
    DEVELOPING --> ARCHIVED: False positive/Merged
    
    ARCHIVED --> [*]
```
```mermaid
stateDiagram-v2
    [*] --> DEVELOPING : Clustering creates new Story
    note right of DEVELOPING
        ID: tmp_evt_&lt;uuid&gt;
    end note
    
    DEVELOPING --> MONITORING : Rules Engine (Health > Threshold)
    note right of MONITORING
        Canonical ID Assigned!
        ID: evt_&lt;base32&gt;
    end note
    
    MONITORING --> STABLE : Rules Engine (No new updates)
    STABLE --> ARCHIVED : Manual or Time-based
    
    DEVELOPING --> ARCHIVED : Cluster rejected/invalidated
```

---

## 3. Observability Metrics
The `EventIdentityService` maintains the following metrics to monitor the health of the canonicalization pipeline:
- `tmp_ids_created`: Volume of initial noisy clusters.
- `canonical_ids_created`: Volume of mature, verified stories.
- `aliases_created`: Tracks the frequency of late-stage story merges.
- `merges_handled`: Total merge operations processed.
