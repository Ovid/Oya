# **Phase 1 Analysis in the Oya Codebase**

Phase 1 Analysis is the first phase of Oya's 8-phase generation pipeline and is responsible for scanning the repository and extracting code structure without making any LLM calls. It's a purely code-based analysis phase that provides foundational data for all subsequent phases.

## **What It Does**

Phase 1 Analysis performs repository scanning and code parsing. It is implemented in the \_run\_analysis() method of the GenerationOrchestrator class. orchestrator.py:492-502

The phase executes the following operations:

1. File Filtering: Uses FileFilter to scan the repository while respecting .oyaignore patterns and default exclusions (like node\_modules, .git, build artifacts, etc.) orchestrator.py:504-506  
2. File Tree Building: Creates a string representation of the repository's file structure orchestrator.py:511  
3. File Parsing: Iterates through each file to read its content and parse it for symbols using language-specific parsers orchestrator.py:526-550  
4. Progress Tracking: Emits progress updates every 10 files to provide user feedback during long-running operations orchestrator.py:552-562

## **Main Components and Responsibilities**

### **FileFilter Component**

The FileFilter class is responsible for determining which files should be included in the analysis. It handles:

* Default exclusions: A predefined list of patterns for common non-source directories and files (hidden files, dependencies, build outputs, Oya artifacts) file\_filter.py:28-51  
* Allowed paths: Explicitly allows certain paths even if they match exclusion patterns (e.g., .oyawiki/notes for user corrections) file\_filter.py:53-57  
* .oyaignore support: Reads custom exclusion patterns from .oyawiki/.oyaignore file\_filter.py:84-90  
* Binary file detection: Excludes binary files by checking for null bytes file\_filter.py:137-151  
* Size filtering: Excludes files larger than 500KB by default file\_filter.py:66-77

### **ParserRegistry Component**

The ParserRegistry selects and applies the appropriate parser for each file based on its extension:

* Language-specific parsers: Includes parsers for Python, TypeScript, Java, with a fallback parser for unsupported languages registry.py:21-28  
* Symbol extraction: Parsers extract various symbol types including functions, classes, methods, imports, exports, routes, CLI commands, interfaces, type aliases, enums, and decorators models.py:7-22  
* Fallback mechanism: If no specific parser matches, uses a generic fallback parser registry.py:38-42

## **Data Structures Produced**

Phase 1 Analysis returns a dictionary containing four key data structures: orchestrator.py:564-569

### **1\. Files List**

A sorted list of relative file paths that passed the filtering criteria.

### **2\. Symbols List**

A list of dictionaries, where each dictionary represents a parsed symbol with the following fields:

* name: Symbol name  
* type: Symbol type (function, class, method, etc.)  
* file: File path where the symbol is defined  
* line: Line number  
* decorators: List of decorator names orchestrator.py:539-547

### **3\. File Tree**

A string representation of the repository's directory structure, used for displaying the project organization in later phases. orchestrator.py:571-593

### **4\. File Contents**

A dictionary mapping file paths to their text content, used by subsequent phases for detailed analysis. orchestrator.py:508-532

## **Current Limitations and Areas for Improvement**

### **1\. Limited Language Support**

The parsing system currently has dedicated parsers only for Python, TypeScript, and Java. registry.py:21-27 Other languages fall back to generic parsing, which may not extract language-specific symbols accurately.

### **2\. Parse Error Handling**

When a file cannot be parsed, it is silently skipped with a bare except Exception block. orchestrator.py:548-550 This approach:

* Doesn't log which files failed to parse or why  
* Provides no feedback to users about parsing issues  
* Could hide important errors

### **3\. File Size Limitation**

The default 500KB file size limit may exclude legitimate source files in some projects. file\_filter.py:66-77 While configurable, this could be made more intelligent (e.g., different limits for different file types).

### **4\. Progress Granularity**

Progress updates only occur every 10 files, which might provide infrequent feedback for repositories with many small files or create uneven progress reporting for repositories with varied file sizes. orchestrator.py:552-562

### **5\. Import Extraction Limitations**

Import extraction is done with simple string matching on the first 50 lines, which is language-specific and limited. orchestrator.py:1059-1084 This approach:

* May miss imports that appear later in the file  
* Uses simple string matching rather than proper parsing  
* Only handles Python, JavaScript/TypeScript, and Java

### **6\. No Incremental Analysis**

Unlike later phases (Files, Directories), Phase 1 Analysis doesn't implement incremental regeneration. It always rescans and reparses all files, even if the repository hasn't changed since the last run.

### **7\. Symbol Type Conversion**

The phase converts ParsedSymbol objects (with SymbolType enum) into plain dictionaries with string type values. orchestrator.py:540-547 This loses type safety and could lead to inconsistencies in later phases.

## **Notes**

Phase 1 Analysis is purely a code analysis phase—it makes no LLM calls, making it fast and deterministic. The data it produces forms the foundation for all subsequent phases in the bottom-up architecture, where Files (Phase 2\) and Directories (Phase 3\) generate documentation that feeds into Synthesis (Phase 4), which then informs the high-level Architecture, Overview, and Workflows pages. orchestrator.py:115-122

