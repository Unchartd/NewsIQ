# Deprecated Components

We list the specific functions, routes, and classes inside active files that are deprecated and should be cleaned up.

## 1. Legacy Story Analysis Pipeline
- **Target File**: [ai_service.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/ai_service.py)
- **Deprecated Class Methods**:
  - `analyze_story()`
  - `_analyze_with_gemini()`
  - `_analyze_with_openai()`
  - `_generate_mock_response()`
- **Deprecated Schemas**:
  - `StoryAIResponse`
  - `TimelineEventSchema` (in `ai_service.py` - replaced by `StoryTimelineEvent` and event extraction schemas)
  - `SourceDifferenceSchema` (in `ai_service.py` - replaced by `StoryDifference` and source comparison schemas)
- **Actions**: Mark as deprecated or delete. Since we are doing a clean repo sweep, we will safely delete these code paths and rewrite associated test assertions.

## 2. Scattered Client Initializations
- **Target Files**:
  - [ner_service_v2.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/ner_service_v2.py)
  - [event_service.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/event_service.py)
  - [entity_linker.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/entity_linker.py)
  - [source_comparison_service.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/source_comparison_service.py)
  - [contradiction_service.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/contradiction_service.py)
- **Deprecated Attributes/Imports**:
  - `self._gemini_client` initialization and `from google import genai`
  - `self._openai_client` initialization and `from openai import AsyncOpenAI`
- **Actions**: Replace with imports of `llm_gateway` and calls to `llm_gateway.execute_request`.
