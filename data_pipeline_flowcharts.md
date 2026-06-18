# NewsIQ Data Processing Pipeline & Crawler Architecture

This document maps out how NewsIQ ingests, vectorizes, clusters, and processes articles from raw sources to AI-structured news intelligence.

---

## 1. High-Level System Architecture

The NewsIQ pipeline is split into four distinct phases orchestrated by Celery background workers:
1. **Ingestion & Crawling** (RSS Feeds & GNews API)
2. **Vectorization & Indexing** (Gemini Embeddings + Qdrant)
3. **Clustering** (Real-time incremental matching & Batch HDBSCAN)
4. **AI Synthesis & Enrichment** (Gemini-2.5-Flash + Named Entity Recognition)

```mermaid
graph TD
    subgraph Phase 1: Ingestion
        A1[Active Sources RSS] -->|httpx / feedparser| B1[Ingestion Service]
        A2[GNews API Client] -->|httpx / category polling| B1
        B1 -->|Concurrent Semaphore Check| Crawl[Crawler Service: newspaper4k / trafilatura / readability / custom-bs4]
        Crawl -->|Save Full-text / Fallback Summary| C1[PostgreSQL: Article Table]
    end

    subgraph Phase 2: Embedding
        C1 -->|Status: pending| B2[Embedding Service]
        B2 -->|Model: text-embedding-004| D2[Generate 3072-dim Vector]
        D2 -->|Upsert| E2[(Qdrant Vector DB)]
        E2 -->|Status: completed| C1
    end

    subgraph Phase 3: Clustering
        C1 -->|Incremental Link| B3[Clustering Service]
        E2 -->|Real-time Cosine Search| B3
        B3 -->|Similarity >= 0.80| F3[Merge Into Existing Story]
        B3 -->|Similarity < 0.80| G3[Batch HDBSCAN Clustering]
        F3 --> H3[PostgreSQL: Story Table]
        G3 --> H3
    end

    subgraph Phase 4: AI Synthesis
        H3 --> B4[AI Service & NER]
        B4 -->|Model: gemini-2.5-flash| D4[Extract Summaries, Facts & Gaps]
        B4 -->|NER Service| E4[Extract People, Orgs & Places]
        D4 -->|Save| F4[PostgreSQL: Story Details, Coverage, Differences]
        E4 -->|Save| F4
        F4 --> G4[Index in Meilisearch & Invalidate Redis Cache]
    end
```

---

## 2. Ingestion & Crawler Flow

The Ingestion pipeline runs on schedule or can be triggered via the API gateway. It ensures that duplicate articles are eliminated at the network edge via URL canonicalization before they are stored in the database.

```mermaid
flowchart TD
    Start([Start Ingestion Run]) --> FetchActive[Query Active Sources in DB]
    FetchActive --> TaskSpawn{Ingestion Mode}
    
    TaskSpawn -->|RSS| RSSFork[Fetch RSS feeds concurrently]
    TaskSpawn -->|GNews| GNewsFork[Fetch headlines via GNews API]
    
    RSSFork --> ParseRSS[Parse XML via feedparser]
    GNewsFork --> NormalizeGNews[Normalize JSON payload]
    
    ParseRSS --> LoopArticles[For each article entry]
    NormalizeGNews --> LoopArticles
    
    LoopArticles --> CanonicalURL[Normalize and Canonicalize URL]
    CanonicalURL --> CheckDB{URL exists in DB?}
    
    CheckDB -- Yes --> Skip[Skip / Deduplicated]
    CheckDB -- No --> IngestionCrawl{Crawl URL concurrently?}
    
    IngestionCrawl -->|Try newspaper4k| NP[newspaper4k]
    NP -->|Success >= 150 chars| ExtractContent[Extract full text, author, image, date]
    NP -->|Fail| TF[trafilatura]
    TF -->|Success >= 150 chars| ExtractContent
    TF -->|Fail| RD[readability-lxml]
    RD -->|Success >= 150 chars| ExtractContent
    RD -->|Fail| BS[Custom BS4 Cleaner]
    BS -->|Success >= 150 chars| ExtractContent
    BS -->|Fail / Empty| FeedFallback[Fallback to RSS / GNews summary]
    
    ExtractContent --> SaveDB[Insert into PostgreSQL Article table]
    FeedFallback --> SaveDB
    
    SaveDB --> SetStatus[Set embedding_status = 'pending']
    SetStatus --> LoopArticles
    LoopArticles -->|End of Batch| SuccessNotify{New Articles Ingested?}
    
    SuccessNotify -- Yes --> TriggerEmbed[Trigger Embedding Task]
    SuccessNotify -- No --> Finish([Done])
    TriggerEmbed --> Finish
```

---

## 3. Vectorization & In-Memory Matching

When new articles are ingested, the system generates high-dimensional vector representations. If a new article is semantically similar to an existing story, it is immediately merged in real-time, bypassing the need for a full batch cluster run.

```mermaid
flowchart TD
    Start([Start Embedding Task]) --> FetchPending[Query first 50 articles where embedding_status = 'pending']
    FetchPending --> CheckEmpty{Articles found?}
    
    CheckEmpty -- No --> Done([Done])
    CheckEmpty -- Yes --> LoopBatch[For each pending article]
    
    LoopBatch --> SetProcessing[Set embedding_status = 'processing']
    SetProcessing --> ConcatText[Combine Headline + Description]
    
    ConcatText --> GenEmbed[Generate 3072-dim Embedding Vector]
    GenEmbed --> Gemini[Gemini text-embedding-004 Client]
    Gemini --> UpsertQdrant[Upsert Vector + Metadata to Qdrant]
    
    UpsertQdrant --> SetCompleted[Set embedding_status = 'completed' in DB]
    
    SetCompleted --> RealTimeMatch[Query Qdrant for similar articles]
    RealTimeMatch --> ScoreThreshold{Cosine Similarity >= 0.80?}
    
    ScoreThreshold -- Yes --> GetStory[Lookup matching article's Story ID]
    GetStory --> StoryExists{Story ID found?}
    
    StoryExists -- Yes --> MergeStory[Merge Article into Story & Regenerate AI Content]
    StoryExists -- No --> Next[Next Article]
    ScoreThreshold -- No --> Next
    MergeStory --> Next
    
    Next --> LoopBatch
    LoopBatch -->|End of Batch| BatchCheck{Processed full 50 batch?}
    
    BatchCheck -- Yes --> TriggerSelf[Queue next embedding batch]
    BatchCheck -- No --> TriggerBatchCluster[Trigger Batch HDBSCAN Clustering Task]
    
    TriggerSelf --> Done
    TriggerBatchCluster --> Done
```

---

## 4. Clustering & AI Synthesis Flow

Unmerged articles are grouped using density-based clustering (HDBSCAN). Once clusters (stories) are formed, Gemini synthesizes the story details, extracts timelines, identifies differences across sources, extracts named entities, and indexes them for search.

```mermaid
flowchart TD
    Start([Start Clustering Task]) --> FetchUnclustered[Query completed, unclustered Articles]
    FetchUnclustered --> RunHDBSCAN[Run HDBSCAN on vector coordinates]
    
    RunHDBSCAN --> GroupClusters[Group articles into Story clusters]
    GroupClusters --> LoopStories[For each cluster]
    
    LoopStories --> CreateStory[Create/Retrieve Story record]
    CreateStory --> GatherArticles[Extract text content from all source articles]
    
    GatherArticles --> AIService[Send articles payload to Gemini 2.5 Flash]
    AIService --> GenAIContent[Generate: Headline, 3 Summary Depths, Key Facts, Timeline]
    AIService --> GenDifferences[Generate: Source Gaps, Contradictions, and Biases]
    
    GenAIContent & GenDifferences --> SaveDetails[Update Story, Timeline, differences, coverage tables]
    
    SaveDetails --> NER[Run Named Entity Recognition on corpus]
    NER --> SaveEntities[Extract entities & save top tags to DB]
    
    SaveEntities --> IndexMeilisearch[Build doc and index in Meilisearch]
    IndexMeilisearch --> InvalidateCache[Invalidate Redis cache for Story ID]
    
    InvalidateCache --> LoopStories
    LoopStories -->|End of Clusters| Finish([Done])
```
