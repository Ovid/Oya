# **QAService Design Limitations and Potential Improvements**

Based on my analysis of the QAService implementation, here are the specific design limitations, potential improvements, and known issues:

## **1\. Evidence Gating: Rigid Thresholds**

The evidence gating mechanism uses hardcoded thresholds that may not be appropriate for all query types:

* MIN\_EVIDENCE\_RESULTS \= 2: Requires at least 2 results service.py:13  
* MAX\_DISTANCE\_THRESHOLD \= 0.8: Distance threshold for relevance service.py:16

Limitations:

* The threshold of 0.8 is arbitrary and not tuned for ChromaDB's specific distance metric  
* Requiring exactly 2 "relevant" results is inflexible \- some questions legitimately need only 1 authoritative source, while others need many  
* No consideration of result quality distribution (e.g., having 2 mediocre results at 0.79 distance passes, but 1 excellent result at 0.1 distance fails) service.py:146-164

Potential Improvements:

* Make thresholds configurable per-deployment  
* Use a weighted relevance score instead of hard cutoffs  
* Consider the gap between top results (if the best result is 0.1 and the second is 0.7, that's very different from 0.7 and 0.75)

## **2\. Context Formatting: Naive Truncation**

The context building has a crude 2000-character hard limit per result: service.py:181

Limitations:

* Uses character count instead of actual token estimation (the codebase has estimate\_tokens() in chunking.py but doesn't use it here)  
* No intelligent truncation \- just cuts off mid-sentence at 2000 characters  
* Doesn't account for the total context window \- could easily exceed model limits with 10 results × 2000 chars each  
* No consideration of which parts of the content are most relevant to the query service.py:166-194

Comparison with synthesis.py:  
The SynthesisGenerator uses a more sophisticated approach with token estimation and batching logic to handle context limits properly. synthesis.py:19-23 synthesis.py:78-99

Potential Improvements:

* Use estimate\_tokens() from the chunking module  
* Implement smart truncation that preserves semantic boundaries  
* Track cumulative token count and prioritize higher-ranked results  
* Consider implementing batching like the synthesis generator if context exceeds limits

## **3\. Search Result Limits: Fixed and Untuned**

The search uses a fixed limit of 10 results with no dynamic adjustment: service.py:54-68

Limitations:

* The limit=10 is hardcoded in the search() method signature  
* No distinction between simple queries (might need fewer results) and complex queries (might benefit from more)  
* The FTS5 query uses the same limit as semantic search, which may not be optimal for keyword matching  
* Results are sorted by type priority then distance, but no consideration of score diversity service.py:140-143

## **4\. Citation Extraction: Fragile Regex Parsing**

The citation extraction relies on brittle regex pattern matching: service.py:196-256

Limitations:

* Expects a specific \[CITATIONS\] format from the LLM, which is not guaranteed service.py:214  
* Regex pattern may fail if the LLM adds extra whitespace or formatting variations  
* Fallback behavior simply uses top 3 results without any attempt to match them to claims in the answer service.py:244-254  
* No validation that cited paths actually exist in the search results  
* Line number parsing is very simplistic (only handles path:lines format)

Potential Improvements:

* Use structured output (JSON) instead of markdown-based citation markers  
* Parse inline citation markers \[1\], \[2\] as mentioned in the design doc but not implemented 2026-01-08-oya-v1-design.md:261-263  
* Validate citations against source results to prevent hallucination  
* Handle multiple citation formats gracefully

## **5\. Error Handling: Silent Failures Degrade Quality**

The service has multiple silent failure modes that degrade answer quality without user awareness:

Silent Search Failures: service.py:104-106 service.py:136-138

If semantic search fails, it silently continues with FTS only. If FTS fails, it continues with semantic only. Users have no way to know their search was degraded.

Generic LLM Error Handling: service.py:302-314

The error message only shows str(e) which may not be actionable for users. Different error types (authentication, rate limits, connection) are all treated the same.

Context Filter Not Implemented: service.py:74-77

The page context filtering feature is stubbed out and does nothing, despite being part of the API contract.

Potential Improvements:

* Log warnings for partial search failures and indicate degraded mode in response  
* Differentiate LLM error types (rate limit vs auth vs connection) and provide specific recovery suggestions  
* Implement the context filtering or remove it from the API  
* Add retry logic with exponential backoff for transient failures  
* Track and expose search quality metrics (e.g., "searched 2/2 indexes successfully")

## **6\. Additional Issues Not in Original Query**

No Token Budget Management:  
The service doesn't track or limit the total prompt size before calling the LLM. With the default max\_tokens=4096 for responses and no input validation, you could easily exceed model context windows. client.py:128-144

Temperature Not Tuned:  
Uses temperature=0.5 which may be too high for factual Q\&A where deterministic answers are preferred. service.py:302-307

No Result Deduplication:  
While paths are deduplicated, the same content from different sources (e.g., code file vs its generated wiki page) could appear multiple times, wasting context window.

## **Notes**

The QAService implementation appears to be a functional MVP but lacks the production-grade robustness found in other parts of the codebase (like the SynthesisGenerator). The most critical improvements would be:

1. Replace hard truncation with proper token budgeting using the existing estimate\_tokens() utility  
2. Implement structured citation extraction instead of regex parsing  
3. Add comprehensive error handling with user-actionable messages  
4. Make thresholds configurable rather than hardcoded constants

The design document suggests more sophisticated features (like inline citation markers, provenance viewer) that aren't yet implemented. 2026-01-08-oya-v1-design.md:236-284

