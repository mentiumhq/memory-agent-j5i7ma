# Memory Agent

## WHY - Vision & Purpose

### Purpose & Users

**What problem are we solving and for whom?**  
We are building a “Memory Agent” as a Temporal workflow to store and retrieve preprocessed documents (Markdown or JSON). Multiple retrieval strategies are supported, including an LLM-based approach that relies solely on a Large Language Model (e.g., GPT-4) for selecting the most relevant documents without embeddings. This approach taps into the LLM’s strong contextual reasoning abilities, allowing it to handle complex queries and nuanced relationships between documents.

- **What does your application do?**  
  Provides a unified data layer that LLM-based agents can query. The Memory Agent retrieves documents from local storage or S3 and can present them to the LLM-based reasoning process. The LLM then interprets the query, understands subtle instructions, and selects the most pertinent documents for the requesting agent.

- **Who will use it?**

  - Internal LLM-based agents and the Executor orchestrating them.

  - Developers or researchers evaluating different retrieval methodologies (Vector, LLM-only, Hybrid, RAG+KG) to determine which best fits their complexity and accuracy needs.

- **Why use it instead of alternatives?**  
  The LLM-based retrieval method excels at complex, context-heavy queries where embeddings alone may not capture the nuance. It leverages the LLM’s ability to reason about relationships, instructions, and subtle differences in data. This can yield higher accuracy in complex workflows, especially when token limits aren’t exceeded.

## WHAT - Core Requirements

### Functional Requirements

System must:

- **Data Retrieval & Storage**

  - Store Markdown/JSON documents locally (using SQLite or JSON files) and in S3 via Temporal activities.

  - Provide four retrieval modes:

    1. **Vectorization + Embedding-Based Search**

    2. **LLM-Based Selection (No Vectorization)**

    3. **Hybrid (Vector + LLM)**

    4. **RAG + Knowledge Graphs**

- **LLM-Based Retrieval Details**

  - System must allow the LLM-based approach to:

    - Fetch candidate documents from local store or S3 (if not cached).

    - Provide these candidates to the LLM as context, along with the query instructions.

    - Let the LLM reason over the documents to select the most relevant subset.

    - Return the final selection to the agent as per Pydantic output schemas.

- **Temporal Workflow Integration**

  - Implement the Memory Agent as a Temporal workflow.

  - Activities handle:

    - Fetching and storing documents in S3.

    - Updating local SQLite/JSON indexes.

    - Interfacing with the LLM (e.g., calling an LLM API) for the reasoning step in the LLM-based retrieval mode.

- **Structured Input/Output with Pydantic**

  - Use Pydantic models for requests/responses (e.g., `GetRequestModel`, `SearchRequestModel`).

  - Validate that outputs (including selected documents by the LLM approach) conform to `GetResponseModel` or `SearchResponseModel`.

- **No Front-End Requirements**

  - All interactions occur via Temporal workflow signals/queries or direct code-level integration.

## HOW - Planning & Implementation

### Technical Implementation

**Required Stack Components**

- **Backend:**

  - Python-based Temporal workflow and activities.

  - Local storage: SQLite or JSON for indexing, minimal caching.

  - S3 integration for long-term, large object storage.

  - LLM Integration:

    - A function or activity that queries a language model (e.g., OpenAI’s API or a local LLM) to reason over candidate documents.

- **Integrations:**

  - S3 for storage.

  - Optional vector DB for embedding-based approaches.

  - Optional knowledge graph layer for the RAG+KG approach.

  - LLM API (HTTP-based) or local LLM runtime accessible by the workflow.

- **Infrastructure:**

  - Temporal server for workflow orchestration.

  - Python workers to run the workflow and activities, including the LLM-based selection step.

**System Requirements**

- **Performance Needs:**

  - LLM-based approach might have higher latency due to API calls and context token limits.

  - System should be prepared to chunk or summarize candidate documents if token limits are approached.

- **Security Requirements:**

  - Secure S3 and LLM API access.

  - Authentication and access control enforced at the workflow/activity level.

- **Scalability Expectations:**

  - As data grows, the LLM-based approach may require strategies like hierarchical selection:

    - Step 1: Retrieve a broad set of candidates (key-based or metadata filtered).

    - Step 2: If too large, chunk or summarize sets before final LLM reasoning.

- **Reliability Targets:**

  - Temporal provides retry and fault tolerance.

  - Fallback to simpler approaches if LLM calls fail.

- **Integration Constraints:**

  - Easily switch retrieval modes at runtime. For LLM-based mode, ensure LLM calls are properly abstracted.

### User Experience (for Agents & Executor)

**Key User Flows (Focusing on LLM-Based Approach)**

1. **LLM-Based Retrieval for a Complex Query**

   - **Entry Point:** Agent requests data with a complex, context-rich query.

   - **Steps:**

     1. Memory Agent receives `SearchRequestModel(query, approach=LLM_ONLY)`.

     2. Memory Agent fetches potentially relevant documents (e.g., by metadata or a broad filter).

     3. Memory Agent sends the query + candidate documents to the LLM, possibly segmented if token limits are an issue.

     4. LLM reasons over the documents, selecting the ones that best answer the query.

     5. Memory Agent returns a `SearchResponseModel` with the chosen documents.

   - **Success Criteria:** The returned documents are contextually aligned with the query’s intent, reflecting the LLM’s reasoning capabilities.

2. **Handling Token Limitations**

   - If the set of candidate documents is large:

     - System may chunk documents or summarize large sets.

     - The LLM might be invoked in multiple passes:

       - Pass 1: Narrow down from a large set to a smaller subset.

       - Pass 2: Select final, most relevant documents.

   This ensures that even large memory sets can be navigated by the LLM.

3. **Executor Updating Data**

   - Executor stores or updates documents (as in other modes).

   - LLM-based approach doesn’t need re-indexing as embeddings or KG do, but may store minimal metadata (like tags) for initial filtering before LLM reasoning.

### Business Requirements

**Access & Authentication**

- **User Types:**

  - Internal agents or Executor.

- **Authentication Requirements:**

  - Ensure only authenticated workflows/agents can request LLM-based retrieval.

**Business Rules**

- **Data Validation Rules:**

  - Documents must match `DocumentModel` schema.

  - Requests validated against Pydantic models.

- **No Additional Compliance or UI Requirements**

  - Focus is on implementing functionality.

### Implementation Priorities

- **High Priority:**

  - Implement Temporal workflow and Pydantic schemas.

  - Integrate LLM-based retrieval method:

    - Activity to call LLM API with query + candidate docs.

    - Handling token constraints.

  - Implement other approaches (Vector, Hybrid, RAG+KG) for comparison.

- **Medium Priority:**

  - Optimize document retrieval pipelines.

  - Implement chunking or summarization strategies if token limits arise.

- **Lower Priority:**

  - Advanced caching or indexing strategies for LLM mode since no embeddings are needed.

----------

## Deliverables

1. **Codebase:**

   - Temporal workflow code.

   - Activities for:

     - S3 storage and retrieval.

     - Local indexing (SQLite/JSON).

     - LLM-based reasoning activity (calls LLM, provides prompt, receives selected docs).

   - Four retrieval strategies:

     - Vector-only

     - LLM-only

     - Hybrid (Vector + LLM)

     - RAG+KG

2. **Pydantic Models:**

   - `DocumentModel`, `GetRequestModel`, `GetResponseModel`, `SearchRequestModel`, `SearchResponseModel`, `StoreRequestModel`, `StoreResponseModel`, and `ApproachEnum`.

   - For LLM-based approach, models will define how candidate docs and queries are packaged to the LLM activity and how results are returned.

3. **Test Files:**

   - Test dataset (Markdown/JSON) in S3.

   - `test_memory_agent.py`:

     - Inserts sample documents.

     - Runs queries in all four modes, including complex queries for LLM-based retrieval.

   - `test_judge.py`:

     - Uses an external LLM “Judge” to score returned documents for relevance and accuracy.

     - Compares LLM-only approach results to vector-only, hybrid, and RAG+KG approaches.

4. **Detailed Scenarios for LLM-Based Retrieval:**

   - Complex query scenario where relationships between documents matter (e.g., multi-step instructions or cross-referencing multiple files).

   - Large memory scenario testing token limit handling.