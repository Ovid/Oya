# **Architectural Reconstruction and Strategic Roadmap for Oya: Transitioning from Naive RAG to Graph-Based Code Intelligence**

## **1\. Executive Analysis of the Current Code Intelligence Landscape**

The development of automated documentation and code intelligence tools has reached an inflection point, transitioning from simple file-based retrieval systems to complex, reasoning-capable architectural assistants. Your initiative to develop "Oya" as an open-source alternative to DeepWiki places you directly at the forefront of this shift. However, the frustrations you have encountered with existing solutions—specifically the "poor quality output," "handwavy diagrams," and inexplicable language hallucinations observed in deepwiki-open—are not merely implementation bugs. They are symptomatic of a fundamental architectural deficiency prevalent in the first generation of AI coding tools: the reliance on "Naive RAG" (Retrieval-Augmented Generation) for domains that inherently require structured, graph-based understanding.

This report provides an exhaustive deconstruction of the deepwiki-open architecture to identify the root causes of its failure modes. It then establishes a theoretical framework for "Code Intelligence" that transcends simple text processing, leveraging advanced concepts such as Abstract Syntax Trees (ASTs), Contextually-Guided Retrieval Augmented Generation (CGRAG), and GraphRAG. Finally, it presents a comprehensive, multi-phase engineering roadmap for Oya, designed to resolve the "mess" of file-centric analysis and establish a robust, structure-aware system capable of generating high-fidelity architectural insights.

### **1.1 The "Vibe Coding" Phenomenon and Its Consequences**

To understand why deepwiki-open exhibits such fragility, one must first analyze its provenance. The project emerged largely as a reaction to the viral marketing of "DevinAI," with the open-source alternative positioning itself as a "rebuild of DevinAI's $300K DeepWiki in 60 minutes".1 While this narrative served to generate significant initial interest and GitHub stars 1, the "60-minute" development philosophy inevitably prioritized speed of deployment over architectural rigor. The result is a system that functions essentially as a wrapper around standard Large Language Model (LLM) APIs, relying on the model's inherent knowledge rather than a deep, intrinsic understanding of the codebase it is analyzing.

The phenomenon often referred to as "vibe coding"—where developers rely on the stochastic capabilities of LLMs to bridge gaps in logic rather than deterministic engineering—explains the "poor quality output" you observed. When a tool relies solely on an LLM to "figure out" the architecture from a bag of text chunks, the output is probabilistic. If the model "feels" like a connection should exist between two modules based on its training data (which might include thousands of similar-looking boilerplates), it will assert that connection, regardless of whether it actually exists in the specific repository under analysis. This leads to the "handwavy" diagrams 2 that look plausible at a glance but crumble under technical scrutiny.

For Oya to succeed where DeepWiki failed, it must reject this stochastic approach in favor of deterministic static analysis. The "mess" of files and directories must be organized not by an LLM's intuition, but by the hard mathematical reality of the code's syntax tree and dependency graph.

## ---

**2\. Forensic Deconstruction of DeepWiki-Open**

A rigorous post-mortem of the deepwiki-open repository reveals the specific mechanisms that lead to the user experience failures you reported. This analysis is based on a review of the project's documentation, issue trackers, and architectural descriptions available in the public domain.

### **2.1 The "Naive RAG" Architecture and the Context Gap**

The primary reason deepwiki-open struggles with "workflows or overall architecture" is its reliance on a linear, text-based ingestion pipeline, often described as "Naive RAG."

#### **2.1.1 The Mechanics of Failure**

In the deepwiki-open architecture, the ingestion process treats code as unstructured text. The system clones a repository and iterates through files, splitting them into chunks based on token counts or simple delimiters.3 These chunks are then embedded using models like nomic-embed-text or OpenAI’s text embeddings and stored in a vector database such as FAISS.5

When a user asks a question about architecture—for example, "Trace the user authentication flow"—the system performs a vector similarity search. It looks for chunks containing terms like "authentication," "login," or "user."

* **The Semantic Gap:** Standard embedding models are trained primarily on natural language, not code execution paths. The vector for a function definition def login(): might be semantically close to the word "authentication," but the vector for a database configuration file db\_config.py (which is critical to the flow) might be far away in vector space if it lacks those specific keywords.  
* **The Context Window Limitation:** Because the retrieval is disconnected, the LLM receives a fragmented view of the system—isolated islands of code without the connecting bridges. It sees the login function and the user table, but misses the middleware, the event listeners, and the external service calls that actually constitute the "workflow."

Consequently, the LLM is forced to hallucinate the missing links to provide a coherent answer. This explains why the tool "mostly understands files and directories"—because files are the unit of storage—but fails at architecture, which is the *relationship* between those units.

### **2.2 The "Chinese Output" Anomaly: A Case Study in Prompt Leakage**

You specifically noted that deepwiki-open "sometimes wrote in Chinese instead of English." This is a severe reliability issue for an English-centric development tool. Forensic analysis of the project's GitHub issues and configuration files isolates this bug to a failure in **Prompt Engineering Governance**.

#### **2.2.1 The Hardcoded "System 1" Prompt**

The most critical evidence comes from error logs where users reported "No valid XML found".5 These logs revealed a hardcoded system prompt injected into the pipeline during the wiki structure generation phase. The prompt explicitly contained the instruction:

*"IMPORTANT: The wiki content will be generated in Mandarin Chinese (中文) language."* 5

This instruction appears to be a vestige of the original development process, likely left by a contributor or the original author who used Chinese as their primary language. In many LLM architectures, "System Prompts" (instructions defining the AI's behavior) carry significantly more weight than "User Prompts." Even if the user configures the UI to English, this hidden system instruction acts as a constitutional override, forcing the model to pivot to Chinese, especially when the model's confidence is low or the context is ambiguous.

#### **2.2.2 Configuration Fragility and Model Bias**

The issue is exacerbated by the system's configuration management. The project uses a file api/config/embedder.json to manage model settings.7

* **Model Mismatch:** The default configuration often points to models like qwen (Qwen is a high-performance model from Alibaba, optimized for Chinese and English) or utilizes embedding models that may have a bias toward Chinese tokens if not strictly clamped.5  
* **The "Default" Fallback:** A pull request (PR \#149) identified that when a specific model was not selected or when the configuration failed to load, the system fell back to an unconfigured state that exposed these raw, hardcoded prompts.8  
* **The XML Parsing Failure:** The prompt instructed the model to return XML. However, because the model was confusing instructions (English query vs. Chinese system prompt), it often polluted the XML output with conversational text in Chinese, breaking the parser and causing the "poor quality" errors you observed.

Implication for Oya:  
This failure mode highlights a non-negotiable requirement for Oya: Strict separation of prompts from code. Prompts must never be hardcoded strings inside Python logic. They should be external resources (e.g., Jinja2 templates) that are dynamically loaded, with the target language passed as a strictly typed variable. Furthermore, automated regression testing must be implemented to ensure that English prompts never contain residual non-English instructions.

### **2.3 The "Handwavy Diagram" Problem**

The user critique regarding diagrams being "too handwavy to be useful" 2 points to another architectural flaw. deepwiki-open generates diagrams by feeding code summaries to an LLM and asking it to generate Mermaid.js syntax.3

* **The Hallucination of Structure:** An LLM does not "see" the code structure; it predicts the next token. If it sees import User, it predicts a relationship. It cannot verify if that import is unused, conditioned on a flag, or part of a comment.  
* **Lack of Determinism:** If you run the same diagram generation task three times in DeepWiki, you will likely get three different diagrams. This indeterminacy renders the tool useless for serious architectural auditing, where precision is paramount.

For Oya, diagrams must be **deterministic**. They should be generated by traversing a verified dependency graph, not by an LLM's creative writing process. The LLM should only be used to *annotate* or *explain* the diagram, not to *construct* its topology.

## ---

**3\. Theoretical Framework: From Text to Graph**

To resolve the "mess" and enable Oya to understand workflows, we must shift the fundamental paradigm of the application. We must move from treating code as **text** (NLP approach) to treating code as a **graph** (Compiler Theory approach).

### **3.1 The Limitations of Vector Embeddings for Code**

Vector embeddings (converting text to a numbered list, or vector) are the backbone of modern RAG. They work exceptionally well for prose because prose is resilient to minor changes. The sentences "The cat sat on the mat" and "The feline rested on the rug" are semantically identical and will have high cosine similarity.

Code, however, is brittle.

* **Sensitivity to Syntax:** "user.id" and "user\_id" are semantically related but might be distinct technical entities (one an object property, one a variable). A standard text embedding might treat them as synonyms, blurring the distinction.  
* **The "Manhattan" Problem:** In a codebase, two files might be textually dissimilar (using different variable names, different logic) but architecturally tightly coupled (one inherits from the other). Vector search based on text similarity will place these files far apart in the vector space, meaning the retriever will never find the parent class when analyzing the child class.

This is why DeepWiki fails at "overall architecture." It relies on a retrieval mechanism (Vector Search) that destroys the very structure (links, inheritance, calls) that defines architecture.

### **3.2 The GraphRAG Paradigm**

To capture architecture, Oya must implement **GraphRAG** (Graph Retrieval-Augmented Generation). This involves constructing a Knowledge Graph where:

* **Nodes** represent code entities (Files, Classes, Functions, Variables).  
* **Edges** represent structural relationships (IMPORTS, CALLS, DEFINES, INHERITS, INSTANTIATES).

#### **3.2.1 Why Graphs Solve the "Workflow" Problem**

Consider the query: *"How is the payment processed?"*

* **Naive RAG (DeepWiki):** Finds files containing "payment" and "processed." Might return payment.html and payment\_service.py. It misses the fact that payment\_service.py calls an external API wrapper in stripe\_lib.py because stripe\_lib.py doesn't mention the word "payment."  
* **GraphRAG (Oya):**  
  1. Identifies the node process\_payment in payment\_service.py.  
  2. Traverses the CALLS edges from that node.  
  3. Discovers the link to stripe\_lib.py.  
  4. Traverses WRITES\_TO edges to find database.transactions.  
  5. Retrieves the code for *all* these connected nodes.

The LLM is then presented with a connected subgraph: *"Here is the payment function, the API wrapper it calls, and the database table it updates."* This allows the LLM to describe the *workflow* accurately: "The payment is processed by the service, which invokes the Stripe API and then logs the transaction to the database."

### **3.3 Contextually-Guided Retrieval (CGRAG)**

A further refinement available to Oya is Contextually-Guided RAG (CGRAG).10 This technique addresses the "unknown unknowns" of retrieval.  
In standard RAG, retrieval happens once. In CGRAG, the retrieval is iterative.

1. **Initial Retrieval:** Get the obvious code chunks.  
2. **LLM Critique:** The LLM analyzes these chunks and identifies gaps. *"I see a call to verify\_user but I don't have the definition of that function."*  
3. **Guided Retrieval:** The system performs a second, targeted retrieval for verify\_user.  
4. **Synthesis:** The final answer is generated from the complete set.

This recursive process mimics how a human engineer reads code—jumping from definition to definition—and is essential for generating the "rich in insight" reports you desire.

## ---

**4\. The Strategic Roadmap for Oya**

To transform Oya from its current state ("understanding files") to the desired state ("understanding architecture"), we propose a phased engineering roadmap. This plan moves away from the "Vibe Coding" approach of DeepWiki and embraces a "Compiler-First" architecture.

### **4.1 Phase 1: The Foundation – Static Analysis & Tree-sitter**

The first step is to stop reading files as strings and start reading them as Abstract Syntax Trees (ASTs). This requires integrating **Tree-sitter**.

#### **4.1.1 Why Tree-sitter?**

Tree-sitter 12 is the industry standard for parsing code. Unlike regex or traditional parsers, it is:

* **Incremental:** It can re-parse a file in milliseconds as the user types, making it suitable for real-time tools.  
* **Robust:** It creates a valid tree even if the code has syntax errors (common in work-in-progress branches).  
* **Polyglot:** It supports Python, JavaScript, Go, Rust, Java, and dozens of other languages via a unified API.

#### **4.1.2 Implementation: Semantic Chunking**

Instead of splitting code by line numbers (e.g., "Lines 1-50"), Oya will use Tree-sitter to perform **Semantic Chunking**.14

* **Mechanism:** The parser walks the AST. When it encounters a function\_definition or class\_definition node, it marks that byte range as a single chunk.  
* **Benefit:** This guarantees that a chunk never starts in the middle of a function or cuts off a closing brace. Every chunk sent to the LLM is a syntactically valid, logical unit of code.  
* **Metadata Extraction:** While parsing, Tree-sitter queries can extract critical metadata for the graph:  
  * What functions are called inside this function?  
  * What classes are inherited?  
  * What variables are read/written?

### **4.2 Phase 2: The Structure – Building the Code Knowledge Graph**

Once the code is parsed, the relationships must be stored in a graph structure.

#### **4.2.1 Graph Database Selection**

For an open-source tool like Oya, usability and ease of installation are paramount.

* **Recommendation: NetworkX (Python)**.15  
  * **Pros:** Pure Python, no external dependencies (like Java for Neo4j), runs in-memory, extremely fast for repositories up to \~50k LOC.  
  * **Cons:** Doesn't scale to massive monorepos (millions of lines) without optimization.  
  * **Strategy:** Start with NetworkX for the "Local Mode." If Oya eventually supports "Enterprise Mode," implement an adapter for **Neo4j** or **Memgraph**.18

#### **4.2.2 The Graph Schema**

Oya's graph should define the following schema to capture architecture:

| Node Type | Attributes |
| :---- | :---- |
| **File** | path, language, last\_modified |
| **Module** | name, namespace |
| **Class** | name, docstring, start\_line, end\_line |
| **Function** | name, signature, return\_type, complexity\_score |

| Edge Type | Direction | Meaning |
| :---- | :---- | :---- |
| CONTAINS | File \-\> Class | Structural hierarchy |
| IMPORTS | File \-\> File | Dependency dependency |
| CALLS | Function \-\> Function | Control flow |
| INHERITS | Class \-\> Class | Object-oriented hierarchy |
| INSTANTIATES | Function \-\> Class | Object creation |

#### **4.2.3 Resolving the "Jump to Definition" Problem**

The hardest part of building a code graph is resolution. When main.py calls process(), determining *which* process() function is being called (is it User.process or Order.process?) is difficult in dynamic languages like Python.

* **The "Stack Graphs" Solution:** GitHub developed "Stack Graphs" 19 specifically to solve this for Tree-sitter. It allows precise name binding resolution.  
* **The MVP Solution:** Integrating Stack Graphs can be complex (Rust bindings). A viable starting point for Oya is a **Heuristic Resolver** using NetworkX.  
  1. Parse imports to see which modules are available.  
  2. If process() is called on an object u, and u is an instance of User, look for process in the User class node.  
  3. If ambiguity exists, create "Soft Edges" to all candidates and let the LLM disambiguate based on context during retrieval.

### **4.3 Phase 3: The Intelligence – Hybrid Retrieval & Agentic Reasoning**

With the graph built, Oya can now answer complex queries.

#### **4.3.1 Hybrid Search Strategy**

Oya should implement a retrieval strategy that combines the best of both worlds 21:

1. **Vector Search (Semantic):** Use embeddings to find code comments and docstrings that match the user's *intent* (e.g., "authentication").  
2. **Graph Search (Structural):** Use the graph to find the *dependencies* of the vector results.  
   * *Algorithm:* Perform a "k-hop neighborhood" traversal. If Vector Search returns Node A, fetch all nodes within 2 hops of A.

#### **4.3.2 The "Planner" Agent**

To solve the "plan to figure out how to resolve this mess" request, Oya should implement an Agentic workflow.

* **User Query:** "Refactor the database layer to use async calls."  
* **Oya Planner:**  
  1. *Decompose:* "I need to find all database connection points," "I need to find all synchronous query executions," "I need to identify the async equivalent libraries."  
  2. *Execute:* The agent queries the graph for all functions importing sqlalchemy (or the relevant DB lib).  
  3. *Trace:* It follows the CALLED\_BY edges to find every controller that relies on these DB functions.  
  4. *Report:* It generates a list of "Impacted Files" and a suggested refactoring order, based on the dependency graph (refactor the leaf nodes first).

## ---

**5\. Implementation Details: Technologies & Tools**

To execute this roadmap, specific technology choices must be made. The following table outlines the recommended stack for Oya, contrasted with DeepWiki's choices.

| Component | DeepWiki (Current) | Oya (Recommended) | Justification |
| :---- | :---- | :---- | :---- |
| **Parsing** | Python String Split / LangChain Splitters | **Tree-sitter** (Python Bindings) | Essential for AST-based semantic chunking and graph construction. 12 |
| **Embedding** | nomic-embed-text / OpenAI | **BGE-M3** or **OpenAI text-embedding-3-small** | BGE-M3 has superior multi-lingual and code understanding; avoids "Chinese bias" of Qwen. 7 |
| **Graph DB** | None (Vector Store only) | **NetworkX** (with JSON serialization) | Enables structural analysis. In-memory speed is sufficient for local tools. 15 |
| **Vector DB** | FAISS | **LanceDB** or **ChromaDB** | LanceDB is embedded, serverless, and handles multi-modal data better. FAISS is older and harder to manage. |
| **LLM Orchestration** | AdalFlow / Custom | **LlamaIndex** | LlamaIndex has first-class support for "Tree Indices" and Graph Stores, superior to LangChain for this specific use case. 23 |
| **Prompts** | Hardcoded Strings | **Jinja2 Templates** | strict separation of code and configuration to prevent prompt leakage. |

### **5.1 Fixing the "Chinese Output" Bug: Concrete Steps**

To ensure Oya never repeats DeepWiki's language failure:

1. **Prompt Templating:** Create a directory prompts/. All prompts must be .j2 files.  
2. **Explicit Language Variable:**  
   Python  
   \# Oya Prompt Logic  
   template \= env.get\_template("summarize\_architecture.j2")  
   prompt \= template.render(  
       context=graph\_context,  
       target\_language="English" \# Strictly typed variable  
   )

3. **Sanitized Config:** Use **Pydantic** for configuration validation. If the language field is missing, default to "en". Throw an error if an unknown language code is detected.  
4. **Embedding Model Clamp:** If supporting local models via Ollama, explicitly blacklist models known to have "chatty" behaviors in other languages unless specifically requested. Prefer llama3 or mistral over qwen for English-first environments unless the user explicitly opts in.

## ---

**6\. Conclusion and Immediate Next Steps**

The "mess" you perceive in deepwiki-open—and by extension, the current state of Oya—is the result of applying text-processing logic to a structural engineering problem. DeepWiki's architecture is built on the assumption that code is just another form of literature to be summarized. The reality is that code is a machine, with gears and levers that must be mapped to be understood.

Your path forward with Oya is not to "fix" the file-reading logic, but to replace it with a **parsing** logic. By integrating Tree-sitter, you gain the eyes to see the code's structure. By integrating NetworkX/GraphRAG, you gain the brain to understand its connectivity.

### **Immediate Action Plan (The "First Sprint")**

1. **Audit Oya:** Immediately check your codebase for any hardcoded prompts or "magic strings" inherited from DeepWiki or other inspirations. Ensure strictly English outputs in your base templates.  
2. **Prototype the Parser:** Write a standalone Python script using tree-sitter-python that takes a file path and outputs a list of every function definition and the functions it calls. Do not use an LLM for this; use the AST.  
   * *Success Metric:* The script correctly identifies class A inheriting from class B without hallucinating.  
3. **Visualize the Graph:** Feed the output of your parser into networkx and generate a simple .png visualization of your own Oya codebase. This "self-portrait" of Oya will reveal the tangled dependencies you need to refactor and serve as the first proof-of-concept for your new architecture.

By following this roadmap, Oya will evolve from a simple "repository chatter" into a true **Architectural Intelligence** tool, fulfilling the promise that DeepWiki failed to deliver.

## ---

**7\. Deep Dive: Implementation Specifics for "Oya"**

To ensure this report serves as a complete implementation guide, we will now drill down into the specific code-level strategies for the most complex components of the proposed architecture: The Tree-sitter Parser and the Graph Construction logic.

### **7.1 Detailed Tree-sitter Integration Strategy**

Implementing Tree-sitter 12 requires more than just installing the library; it requires a strategy for "Queries." Tree-sitter uses a Lisp-like query language (S-expressions) to match patterns in the AST.

The Query Pattern for Oya:  
To extract architectural data, you will write queries that capture definitions and references.

* **Python Query Example:**  
  Scheme  
  (class\_definition  
    name: (identifier) @class.name  
    body: (block  
      (function\_definition  
        name: (identifier) @method.name  
        parameters: (parameters) @method.params  
      ) @method.def  
    )  
  ) @class.def

* Extraction Logic:  
  When Oya processes a file, it runs this query.  
  1. It captures @class.name (e.g., "PaymentService").  
  2. It captures @method.name (e.g., "process\_transaction").  
  3. Crucially, it captures the **byte range** of @method.def.  
  4. **Semantic Chunking:** Instead of arbitrarily slicing the file, Oya stores the exact bytes of the function as a chunk. This ensures the LLM sees the *entire* function logic, context, and docstrings in one coherent block.

### **7.2 Building the "Deterministic" Diagram Generator**

The user complaint about "handwavy diagrams" 2 is solved by generating diagrams algorithmically from the graph, not probabilistically via the LLM.

**The Algorithm:**

1. **Subgraph Selection:** Identify the scope. (e.g., "Show me the Auth module").  
2. **Graph Traversal:** Select all nodes in the Auth namespace and their immediate outbound edges.  
3. **Mermaid Generation:**  
   * Iterate through the selected nodes. For each class node, print class {Node.name}.  
   * Iterate through edges.  
     * If edge is INHERITS, print {Source} \<|-- {Target}.  
     * If edge is CALLS, print {Source}..\> {Target} : calls.  
     * If edge is COMPOSES, print {Source} \*-- {Target}.

Result:  
The output is strict, valid Mermaid.js code.

* If AuthService calls Database, the arrow *will* exist.  
* If there is no dependency, no line will be drawn.  
* The LLM's role is restricted to writing the *caption* for the diagram ("Figure 1: The Authentication Service inherits from BaseService and delegates storage to the Database module"), ensuring the description matches the visual reality.

### **7.3 Governance of the "Chinese Output" Bug**

To permanently resolve the language contamination issue, Oya must implement a "Prompt Firewall."

**The Firewall Logic:**

1. **Input Validation:** Before any prompt is sent to the LLM, a pre-flight check scans the rendered prompt string.  
2. **Regex Guardrails:** If the prompt contains non-ASCII characters (and the user language is set to English), the system halts and logs a warning. This catches accidental inclusion of Chinese system prompts or "poisoned" context from the vector store.  
3. **Output Validation:** Use a lightweight classifier or regex check on the *response*. If the response density of Chinese characters exceeds 1%, the response is discarded, and a retry is triggered with a reinforced system instruction ("You must reply in English").  
4. **Embedding Hygiene:**  
   * Audit the vector store. DeepWiki likely has "poisoned" chunks in its index (chunks of Chinese comments or readme files).  
   * Oya should implement a language detector during *ingestion*. If a file is detected as primarily non-English (and the user hasn't enabled multi-lingual support), tag it or exclude it to prevent it from polluting the retrieval context.

### **7.4 Scaling with "GraphRAG" Communities**

As Oya matures, you can implement the advanced "Community Detection" features of GraphRAG.24

* **The Concept:** Use the Leiden algorithm (a graph clustering algorithm) to detect dense clusters of nodes.  
* **Application:** These clusters represent "Modules" or "Components" even if the directory structure doesn't reflect them.  
* **Hierarchical Summarization:**  
  1. Summarize every Function.  
  2. Summarize the Cluster (based on function summaries).  
  3. Summarize the Graph (based on cluster summaries).  
* **Benefit:** This allows Oya to answer high-level questions like "What is the overall architecture of this system?" by reading the high-level cluster summaries, rather than trying to read 10,000 individual files. This is the "Holy Grail" of automated documentation that DeepWiki aimed for but failed to achieve due to its flat, naive architecture.

By methodically implementing these layers—Parser, Graph, Firewall, and Community Detection—Oya will not only resolve the "mess" of the present but establishes a foundation for the future of open-source code intelligence.

#### **Works cited**

1. I Rebuilt DevinAI's $300K DeepWiki in 60 Minutes with Gemini : r/GoogleGeminiAI \- Reddit, accessed January 16, 2026, [https://www.reddit.com/r/GoogleGeminiAI/comments/1kbl94l/i\_rebuilt\_devinais\_300k\_deepwiki\_in\_60\_minutes/](https://www.reddit.com/r/GoogleGeminiAI/comments/1kbl94l/i_rebuilt_devinais_300k_deepwiki_in_60_minutes/)  
2. DeepWiki: Understand Any Codebase \- Hacker News, accessed January 16, 2026, [https://news.ycombinator.com/item?id=45002092](https://news.ycombinator.com/item?id=45002092)  
3. Introduction to DeepWiki-Open, accessed January 16, 2026, [https://asyncfunc.mintlify.app/getting-started/introduction](https://asyncfunc.mintlify.app/getting-started/introduction)  
4. DeepWiki: Why I Open-Sourced an AI-Powered Wiki Generator | by Sj Ng \- Medium, accessed January 16, 2026, [https://medium.com/@sjng/deepwiki-why-i-open-sourced-an-ai-powered-wiki-generator-b67b624e4679](https://medium.com/@sjng/deepwiki-why-i-open-sourced-an-ai-powered-wiki-generator-b67b624e4679)  
5. 错误\~No valid XML found in response · Issue \#325 · AsyncFuncAI/deepwiki-open \- GitHub, accessed January 16, 2026, [https://github.com/AsyncFuncAI/deepwiki-open/issues/325](https://github.com/AsyncFuncAI/deepwiki-open/issues/325)  
6. Architecture Overview \- DeepWiki-Open, accessed January 16, 2026, [https://asyncfunc.mintlify.app/reference/architecture](https://asyncfunc.mintlify.app/reference/architecture)  
7. No valid XML found in response · Issue \#198 · AsyncFuncAI/deepwiki-open \- GitHub, accessed January 16, 2026, [https://github.com/AsyncFuncAI/deepwiki-open/issues/198](https://github.com/AsyncFuncAI/deepwiki-open/issues/198)  
8. Contributing to an Open Source LLM Tool by Accident: My First Medium Post | by Segur, accessed January 16, 2026, [https://medium.com/@segur.opus/contributing-to-an-open-source-llm-tool-by-accident-my-first-medium-post-372387f46b1e](https://medium.com/@segur.opus/contributing-to-an-open-source-llm-tool-by-accident-my-first-medium-post-372387f46b1e)  
9. deepwiki-open/README.md at main \- GitHub, accessed January 16, 2026, [https://github.com/AsyncFuncAI/deepwiki-open/blob/main/README.md](https://github.com/AsyncFuncAI/deepwiki-open/blob/main/README.md)  
10. From Snippets to Systems: Advanced Techniques for Repository-Aware Coding Assistants | by Colin Baird | Medium, accessed January 16, 2026, [https://medium.com/@colinbaird\_51123/from-snippets-to-systems-advanced-techniques-for-repository-aware-coding-assistants-cf1a2086ab41](https://medium.com/@colinbaird_51123/from-snippets-to-systems-advanced-techniques-for-repository-aware-coding-assistants-cf1a2086ab41)  
11. How to generate accurate LLM responses on large code repositories: Presenting CGRAG, a new feature of dir-assistant | by Chase Adams | Medium, accessed January 16, 2026, [https://medium.com/@djangoist/how-to-create-accurate-llm-responses-on-large-code-repositories-presenting-cgrag-a-new-feature-of-e77c0ffe432d](https://medium.com/@djangoist/how-to-create-accurate-llm-responses-on-large-code-repositories-presenting-cgrag-a-new-feature-of-e77c0ffe432d)  
12. Using The Tree-Sitter Library In Python To Build A Custom Tool For Parsing Source Code And Extracting Call Graphs \- volito.digital, accessed January 16, 2026, [https://volito.digital/using-the-tree-sitter-library-in-python-to-build-a-custom-tool-for-parsing-source-code-and-extracting-call-graphs/](https://volito.digital/using-the-tree-sitter-library-in-python-to-build-a-custom-tool-for-parsing-source-code-and-extracting-call-graphs/)  
13. Tree-sitter: Introduction, accessed January 16, 2026, [https://tree-sitter.github.io/](https://tree-sitter.github.io/)  
14. Repository GraphRAG MCP Server: A Deep Dive for AI Engineers, accessed January 16, 2026, [https://skywork.ai/skypage/en/repository-graphrag-mcp-server-ai-engineers/1978326852212269056](https://skywork.ai/skypage/en/repository-graphrag-mcp-server-ai-engineers/1978326852212269056)  
15. Tiny GraphRAG (Part 1\) \- Stephen Diehl, accessed January 16, 2026, [https://www.stephendiehl.com/posts/graphrag1/](https://www.stephendiehl.com/posts/graphrag1/)  
16. Using NetworkX, Jaccard Similarity, and cuGraph to Predict Your Next Favorite Movie, accessed January 16, 2026, [https://developer.nvidia.com/blog/using-networkx-jaccard-similarity-and-cugraph-to-predict-your-next-favorite-movie/](https://developer.nvidia.com/blog/using-networkx-jaccard-similarity-and-cugraph-to-predict-your-next-favorite-movie/)  
17. Deep Clustering of Student Code Strategies Using Multi-View Code Representation (CMVAE) \- MDPI, accessed January 16, 2026, [https://www.mdpi.com/2076-3417/15/7/3462](https://www.mdpi.com/2076-3417/15/7/3462)  
18. GraphRAG for Devs: Graph-Code Demo Overview \- Memgraph, accessed January 16, 2026, [https://memgraph.com/blog/graphrag-for-devs-coding-assistant](https://memgraph.com/blog/graphrag-for-devs-coding-assistant)  
19. tree-sitter-stack-graphs-python \- crates.io: Rust Package Registry, accessed January 16, 2026, [https://crates.io/crates/tree-sitter-stack-graphs-python](https://crates.io/crates/tree-sitter-stack-graphs-python)  
20. Introducing stack graphs \- The GitHub Blog, accessed January 16, 2026, [https://github.blog/open-source/introducing-stack-graphs/](https://github.blog/open-source/introducing-stack-graphs/)  
21. dead8309/graph-rag-indexer: Comparing vector-only RAG with GraphRAG (neo4j+milvus) for semantic and structural code search in JavaScript. \- GitHub, accessed January 16, 2026, [https://github.com/dead8309/graph-rag-indexer](https://github.com/dead8309/graph-rag-indexer)  
22. OSS Code Indexer for Efficient Retrieval \- Archive Project Details | Google Summer of Code, accessed January 16, 2026, [https://summerofcode.withgoogle.com/programs/2025/projects/wIsioRXL](https://summerofcode.withgoogle.com/programs/2025/projects/wIsioRXL)  
23. What is GraphRAG? \- IBM, accessed January 16, 2026, [https://www.ibm.com/think/topics/graphrag](https://www.ibm.com/think/topics/graphrag)  
24. GraphRAG: A Complete Guide from Concept to Implementation \- Analytics Vidhya, accessed January 16, 2026, [https://www.analyticsvidhya.com/blog/2024/11/graphrag/](https://www.analyticsvidhya.com/blog/2024/11/graphrag/)  
25. Intro to GraphRAG, accessed January 16, 2026, [https://graphrag.com/concepts/intro-to-graphrag/](https://graphrag.com/concepts/intro-to-graphrag/)