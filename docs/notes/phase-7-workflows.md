# **Phase 7 Workflows Generation**

## **How It Works**

Phase 7 is the final documentation generation phase (before indexing) that creates individual workflow pages documenting key execution paths through the codebase. The process has two main steps:

### **1\. Workflow Discovery**

The WorkflowDiscovery class identifies entry points from parsed symbols by checking for:

* Decorators: @click.command, @app.get, @router.post, @typer.command, @api\_view, etc.  
* Function names: main, \_\_main\_\_, run, start, serve, execute  
* Symbol types: route, cli\_command workflows.py:36-69

Each entry point is then converted into a DiscoveredWorkflow object containing a name, slug, entry points, and related files: workflows.py:11-25

### **2\. Workflow Generation**

The orchestrator generates up to 10 workflow pages (hard-coded limit), gathering code context from related files: orchestrator.py:724-726

For each workflow, code context is gathered from related files, truncated to 2000 characters per file: orchestrator.py:741-746

## **Context Sources and Data Structures**

Unlike Phase 5 Architecture, Phase 7 does NOT use SynthesisMap. Instead, it relies on:

### **Primary Context:**

1. Raw parsed symbols from Phase 1 analysis  
2. Truncated file contents (2000 chars per file)  
3. Entry point metadata (file path, name, type) orchestrator.py:702-750

### **Prompt Template Structure:**

The WORKFLOW\_TEMPLATE instructs the LLM to generate:

* Workflow Overview  
* Trigger/Entry Point  
* Step-by-Step Flow  
* Key Functions  
* Error Handling  
* Related Workflows prompts.py:240-263

## **Comparison to Phase 5 Architecture**

Phase 5 Architecture uses a much richer context structure via SynthesisMap: orchestrator.py:664-688

The SynthesisMap provides structured data including:

* Layers: Architectural layer groupings with purposes and file lists  
* Key components: Important classes/functions with their roles and layers  
* Dependency graph: Inter-layer dependencies  
* Project summary: LLM-generated overall understanding summaries.py:196-214

In contrast, Phase 7 workflows only receive:

* Raw symbol dictionaries  
* Truncated raw code (not summaries)  
* No layer or component information  
* No dependency relationships

## **Cascade Behavior**

Like Phase 5 and 6, Phase 7 only regenerates when synthesis is regenerated (cascade behavior): orchestrator.py:469-474

## **Is the Context Suitable?**

The current context has significant limitations:

### **Strengths:**

* ✅ Direct access to entry point metadata  
* ✅ Actual code snippets for context  
* ✅ Simple and fast to gather

### **Weaknesses:**

* ❌ No architectural understanding \- workflows don't know which layer components belong to  
* ❌ No dependency tracing \- can't follow call chains through the dependency graph  
* ❌ Truncated code context \- 2000 chars per file is often insufficient  
* ❌ No component role information \- missing the "why" behind components  
* ❌ Simplistic workflow grouping \- one entry point \= one workflow, no intelligent clustering  
* ❌ No file summaries \- uses raw code instead of pre-analyzed summaries

## **Recommended Improvements**

### **1\. Use SynthesisMap for Richer Context**

Pass the SynthesisMap to workflow generation (similar to Architecture and Overview phases): orchestrator.py:421-443

This would provide:

* Layer information for each component in the workflow  
* Component roles and purposes (from key\_components)  
* Architectural context for better documentation

### **2\. Use File Summaries Instead of Raw Code**

Replace truncated raw code with structured FileSummary objects that contain:

* Purpose description  
* Layer classification  
* Key abstractions  
* Dependencies (internal and external) summaries.py:40-63

### **3\. Leverage Dependency Graph for Call Tracing**

Use the SynthesisMap.dependency\_graph to trace execution paths through the codebase: summaries.py:207

This would enable documenting the actual flow of control through layers and components.

### **4\. Intelligent Workflow Clustering**

The current implementation creates one workflow per entry point: workflows.py:119-145

Instead, consider:

* Grouping related entry points by domain/layer  
* Identifying workflows that share common components  
* Using LLM to cluster related execution paths

### **5\. Remove or Increase the Truncation Limit**

The 2000-character truncation is arbitrary and likely insufficient. Consider:

* Using file summaries entirely (structured data)  
* Increasing the limit based on token budgets  
* Selectively including only relevant functions (not entire files)

### **6\. Cross-Reference with Architecture**

Since workflows only regenerate when synthesis changes, they could reference layer information and key components documented in the architecture page, creating better integration across documentation.

## **Notes**

Phase 7 Workflows generation is currently the least sophisticated of the high-level phases (5-7). While Phase 5 (Architecture) and Phase 6 (Overview) both leverage the rich SynthesisMap data structure, Phase 7 relies on raw analysis data similar to the low-level phases. This creates a disconnect where workflow documentation lacks the architectural context available to other high-level documentation.

The most impactful improvement would be to refactor \_run\_workflows() to accept and utilize the SynthesisMap, enabling workflows to document execution paths with full architectural awareness \- showing how requests flow through layers, which key components are involved, and how they relate to the overall system design.

