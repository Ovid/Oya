# **Phase 8 Indexing in Oya**

## **Overview**

Phase 8 Indexing is the final phase of Oya's 8-phase bottom-up wiki generation pipeline. It runs after all content generation phases (Analysis → Files → Directories → Synthesis → Architecture → Overview → Workflows) complete, and is responsible for indexing the generated wiki content to enable search and Q\&A functionality. repos.py:425-436

## **How Phase 8 Works**

### **Execution Flow**

Phase 8 is triggered in the \_run\_generation() background task after the GenerationOrchestrator completes. The system:

1. Updates the database to indicate Phase 8 has started  
2. Creates a VectorStore instance pointing to the staging ChromaDB path  
3. Creates an IndexingService with the vector store, database, and wiki paths  
4. Clears any existing index to ensure fresh data  
5. Calls index\_wiki\_pages() with progress callbacks  
6. Saves embedding metadata (provider and model used)  
7. Promotes staging to production after successful completion repos.py:482-517

### **Progress Tracking**

During indexing, progress is tracked by counting files processed and updating the database with current step counts. Progress updates occur every 10 files or on the last file to avoid excessive database writes. service.py:113-116

## **Data Being Indexed**

### **Wiki Content**

The indexing service processes all markdown files (.md) in the wiki directory. For each file, it extracts:

* Content: The full markdown text  
* Title: Extracted from the first H1 header (\# Title) or derived from filename  
* Path: Relative path from wiki root (e.g., files/src-main-py.md)  
* Type: Page type determined from path structure service.py:84-103

### **Page Type Classification**

The system classifies pages into specific types based on their path:

* overview \- overview.md at root  
* architecture \- architecture.md at root  
* workflow \- files in workflows/ directory  
* directory \- files in directories/ directory  
* file \- files in files/ directory  
* wiki \- any other page service.py:208-227

## **Indexing Strategy**

### **Dual Indexing Approach**

Oya uses a hybrid indexing strategy that combines two complementary search technologies:

#### **1\. Vector Store (ChromaDB) \- Semantic Search**

All wiki pages are indexed into ChromaDB for semantic/vector search. Each document receives:

* A unique ID in format wiki\_{sanitized\_path}  
* Full markdown content as the document  
* Metadata dictionary containing path, title, and type service.py:120-127

ChromaDB automatically generates embeddings using the configured LLM provider's embedding model and stores them for cosine similarity search. store.py:40-57

#### **2\. SQLite FTS5 \- Full-Text Search**

Simultaneously, content is inserted into a SQLite FTS5 (Full-Text Search) virtual table with:

* content \- searchable text  
* title \- page title  
* path \- file path (unindexed)  
* type \- page type (unindexed)

The FTS5 table uses Porter stemming and Unicode tokenization for keyword-based search with BM25 ranking. service.py:105-110 migrations.py:78-86

### **Embedding Metadata Tracking**

To support model switching detection, the system saves metadata about which embedding provider and model were used: service.py:129-131

This metadata includes provider, model, and timestamp, stored in embedding\_metadata.json in the metadata directory. service.py:165-182

## **RAG System Implementation**

### **Hybrid Search**

The Q\&A service implements a hybrid search approach that combines both semantic and full-text search:

1. Semantic Search via ChromaDB: Queries the vector store to find semantically similar documents based on embedding similarity  
2. Full-Text Search via FTS5: Performs keyword-based BM25 search using SQLite's full-text index  
3. Deduplication: Merges results from both sources, removing duplicates by path  
4. Ranking: Sorts results by type priority (notes first) then by relevance score service.py:54-144

### **Evidence Gating**

The RAG system includes evidence gating to ensure answer quality:

* Requires minimum 2 results (MIN\_EVIDENCE\_RESULTS \= 2)  
* Checks that at least 2 results have relevance scores better than threshold (MAX\_DISTANCE\_THRESHOLD \= 0.8 for vector search, lower distance \= more relevant)  
* In "gated" mode, refuses to answer if evidence is insufficient  
* In "loose" mode, provides answer but warns about limited evidence service.py:146-164

### **Answer Generation**

When generating answers:

1. Builds context prompt with top search results (limited to 2000 chars per result)  
2. Sends to LLM with system prompt instructing concise, accurate responses  
3. Extracts citations from the LLM response in \[CITATIONS\] format  
4. Falls back to using top 3 results as citations if none explicitly provided  
5. Adds appropriate disclaimers based on evidence quality and mode service.py:272-331

### **Context Prompt Construction**

The RAG system formats search results as context, with each result labeled by type (FILE, DIRECTORY, WORKFLOW, etc.) and path: service.py:166-194

## **Implementation Architecture**

The indexing and RAG system follows a clean service layer architecture:

The IndexingService class encapsulates all indexing logic, while the QAService handles search and answer generation. service.py:19-48 service.py:34-52

## **Notes**

* Staging Pattern: Phase 8 indexes in a staging directory (.oyawiki-building/meta/chroma) before atomic promotion to production, ensuring users never see partial index states  
* Clear and Reindex: The system clears the entire index before reindexing to avoid stale data from removed or renamed files  
* Model Mismatch Detection: Embedding metadata enables the UI to warn users when the current LLM model differs from what was used to create embeddings, prompting regeneration  
* Batch Processing: Vector store operations are batched for efficiency, with all documents added in a single call after FTS indexing completes  
* No Notes Indexing Yet: Currently only wiki pages are indexed; user notes would need separate handling to be included in the RAG system

