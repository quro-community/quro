#!/usr/bin/env node
/**
 * symbol_probe.js - TypeScript Symbol Analysis Probe
 *
 * Minimal TypeScript probe (<500 lines) for Python quro_cli integration.
 * Uses TypeScript Compiler API with watch mode for incremental updates.
 * Communicates via JSON-RPC over stdio.
 *
 * Architecture:
 * - Watch mode: ts.createWatchCompilerHost for 40-200x faster incremental updates
 * - Symbol fingerprinting: file:line:char:symbol UIDs for cross-file linking
 * - Graceful degradation: Never crashes, returns structured errors with fallback hints
 * - Stdio JSON-RPC: 100x faster than HTTP (0.5-2ms vs 50-100ms)
 */

const ts = require('typescript');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

// === Configuration ===
const DEFAULT_TSCONFIG = 'tsconfig.json';
const WATCH_DEBOUNCE_MS = 100;

// === Global State ===
let program = null;
let typeChecker = null;
let watchHost = null;
let configPath = null;
let rootDir = process.cwd();

// === JSON-RPC Protocol ===

/**
 * Send JSON-RPC response to stdout
 */
function sendResponse(id, result, error = null) {
  const response = {
    jsonrpc: '2.0',
    id,
    ...(error ? { error } : { result })
  };
  console.log(JSON.stringify(response));
}

/**
 * Send JSON-RPC notification (no id)
 */
function sendNotification(method, params) {
  const notification = {
    jsonrpc: '2.0',
    method,
    params
  };
  console.error(JSON.stringify(notification)); // Use stderr for notifications
}

// === TypeScript Compiler Setup ===

/**
 * Initialize TypeScript program with watch mode
 */
function initializeProgram(tsconfigPath) {
  try {
    configPath = path.resolve(tsconfigPath || DEFAULT_TSCONFIG);

    if (!fs.existsSync(configPath)) {
      throw new Error(`tsconfig.json not found at ${configPath}`);
    }

    // Read tsconfig
    const configFile = ts.readConfigFile(configPath, ts.sys.readFile);
    if (configFile.error) {
      throw new Error(ts.formatDiagnostic(configFile.error, formatHost));
    }

    const parsedConfig = ts.parseJsonConfigFileContent(
      configFile.config,
      ts.sys,
      path.dirname(configPath)
    );

    rootDir = parsedConfig.options.rootDir || path.dirname(configPath);

    // Create watch host
    watchHost = ts.createWatchCompilerHost(
      configPath,
      {},
      ts.sys,
      ts.createSemanticDiagnosticsBuilderProgram,
      reportDiagnostic,
      reportWatchStatusChanged
    );

    // Override afterProgramCreate to capture program
    const origAfterProgramCreate = watchHost.afterProgramCreate;
    watchHost.afterProgramCreate = (builderProgram) => {
      program = builderProgram.getProgram();
      typeChecker = program.getTypeChecker();
      sendNotification('program_updated', { timestamp: Date.now() });
      if (origAfterProgramCreate) {
        origAfterProgramCreate(builderProgram);
      }
    };

    // Start watch mode
    ts.createWatchProgram(watchHost);

    return { ok: true };
  } catch (error) {
    return { ok: false, error: error.message };
  }
}

// === Diagnostic Reporting ===

const formatHost = {
  getCanonicalFileName: path => path,
  getCurrentDirectory: ts.sys.getCurrentDirectory,
  getNewLine: () => ts.sys.newLine
};

function reportDiagnostic(diagnostic) {
  // Suppress diagnostics during normal operation
  // Only report via get_diagnostics RPC call
}

function reportWatchStatusChanged(diagnostic) {
  // Suppress watch status messages
}

// === Core Analysis Methods ===

/**
 * Get type information at a specific position
 *
 * @param {string} filePath - Absolute file path
 * @param {number} line - 0-indexed line number
 * @param {number} character - 0-indexed character offset
 * @returns {object} Type information with fingerprint
 */
function getTypeAtPosition(filePath, line, character) {
  try {
    if (!program || !typeChecker) {
      return { error: 'TYPE_CHECKER_NOT_READY', fallback: 'tree-sitter' };
    }

    const sourceFile = program.getSourceFile(filePath);
    if (!sourceFile) {
      return { error: 'FILE_NOT_IN_PROGRAM', fallback: 'tree-sitter', filePath };
    }

    const position = ts.getPositionOfLineAndCharacter(sourceFile, line, character);
    const node = findNodeAtPosition(sourceFile, position);

    if (!node) {
      return { error: 'NO_NODE_AT_POSITION', line, character };
    }

    const type = typeChecker.getTypeAtLocation(node);
    const typeString = typeChecker.typeToString(type);
    const symbol = typeChecker.getSymbolAtLocation(node);

    const result = {
      typeString,
      fingerprint: null,
      kind: ts.SyntaxKind[node.kind],
      flags: type.flags
    };

    if (symbol) {
      result.fingerprint = getSymbolFingerprint(symbol);
      result.symbolName = symbol.getName();
    }

    return result;
  } catch (error) {
    return { error: 'TYPE_ANALYSIS_FAILED', message: error.message, fallback: 'tree-sitter' };
  }
}

/**
 * Find definition location for a symbol
 *
 * @param {string} filePath - Absolute file path
 * @param {number} line - 0-indexed line number
 * @param {number} character - 0-indexed character offset
 * @returns {object} Definition location with fingerprint
 */
function findDefinition(filePath, line, character) {
  try {
    if (!program || !typeChecker) {
      return { error: 'TYPE_CHECKER_NOT_READY', fallback: 'tree-sitter' };
    }

    const sourceFile = program.getSourceFile(filePath);
    if (!sourceFile) {
      return { error: 'FILE_NOT_IN_PROGRAM', fallback: 'tree-sitter', filePath };
    }

    const position = ts.getPositionOfLineAndCharacter(sourceFile, line, character);
    const node = findNodeAtPosition(sourceFile, position);

    if (!node) {
      return { error: 'NO_NODE_AT_POSITION', line, character };
    }

    const symbol = typeChecker.getSymbolAtLocation(node);
    if (!symbol) {
      return { error: 'NO_SYMBOL_AT_POSITION', line, character };
    }

    const declarations = symbol.getDeclarations();
    if (!declarations || declarations.length === 0) {
      return { error: 'NO_DECLARATIONS', symbolName: symbol.getName() };
    }

    const declaration = declarations[0];
    const declSourceFile = declaration.getSourceFile();
    const { line: declLine, character: declChar } = ts.getLineAndCharacterOfPosition(
      declSourceFile,
      declaration.getStart()
    );

    return {
      filePath: declSourceFile.fileName,
      line: declLine,
      character: declChar,
      fingerprint: getSymbolFingerprint(symbol),
      symbolName: symbol.getName(),
      kind: ts.SyntaxKind[declaration.kind]
    };
  } catch (error) {
    return { error: 'DEFINITION_LOOKUP_FAILED', message: error.message, fallback: 'tree-sitter' };
  }
}

/**
 * Resolve import path to absolute file path
 *
 * @param {string} filePath - Source file path
 * @param {string} importPath - Import specifier (e.g., './foo', '@/bar')
 * @returns {object} Resolved path information
 */
function resolveImportPath(filePath, importPath) {
  try {
    if (!program) {
      return { error: 'PROGRAM_NOT_READY', fallback: 'heuristic' };
    }

    const sourceFile = program.getSourceFile(filePath);
    if (!sourceFile) {
      return { error: 'FILE_NOT_IN_PROGRAM', fallback: 'heuristic', filePath };
    }

    // Use TypeScript's module resolution
    const resolvedModule = ts.resolveModuleName(
      importPath,
      filePath,
      program.getCompilerOptions(),
      ts.sys
    );

    if (resolvedModule.resolvedModule) {
      return {
        resolvedPath: resolvedModule.resolvedModule.resolvedFileName,
        isExternalLibrary: resolvedModule.resolvedModule.isExternalLibraryImport || false
      };
    }

    return { error: 'MODULE_NOT_RESOLVED', importPath, fallback: 'heuristic' };
  } catch (error) {
    return { error: 'RESOLUTION_FAILED', message: error.message, fallback: 'heuristic' };
  }
}

/**
 * Get diagnostics for a file
 *
 * @param {string} filePath - Absolute file path
 * @returns {object} Diagnostics information
 */
function getDiagnostics(filePath) {
  try {
    if (!program) {
      return { error: 'PROGRAM_NOT_READY', diagnostics: [] };
    }

    const sourceFile = program.getSourceFile(filePath);
    if (!sourceFile) {
      return { error: 'FILE_NOT_IN_PROGRAM', diagnostics: [], filePath };
    }

    const syntacticDiagnostics = program.getSyntacticDiagnostics(sourceFile);
    const semanticDiagnostics = program.getSemanticDiagnostics(sourceFile);

    const allDiagnostics = [...syntacticDiagnostics, ...semanticDiagnostics];

    const formatted = allDiagnostics.map(diagnostic => {
      const message = ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n');
      let location = null;

      if (diagnostic.file && diagnostic.start !== undefined) {
        const { line, character } = ts.getLineAndCharacterOfPosition(
          diagnostic.file,
          diagnostic.start
        );
        location = { line, character };
      }

      return {
        category: ts.DiagnosticCategory[diagnostic.category],
        code: diagnostic.code,
        message,
        location
      };
    });

    return { diagnostics: formatted };
  } catch (error) {
    return { error: 'DIAGNOSTICS_FAILED', message: error.message, diagnostics: [] };
  }
}

/**
 * Extract call graph from a file
 *
 * @param {string} filePath - Absolute file path
 * @returns {object} Call graph information
 */
function extractCallGraph(filePath) {
  try {
    if (!program || !typeChecker) {
      return { error: 'PROGRAM_NOT_READY', calls: [] };
    }

    const sourceFile = program.getSourceFile(filePath);
    if (!sourceFile) {
      return { error: 'FILE_NOT_IN_PROGRAM', calls: [], filePath };
    }

    const calls = [];
    let currentFunction = null;

    function visit(node) {
      // Track current function context
      if (ts.isFunctionDeclaration(node) || ts.isMethodDeclaration(node) || ts.isArrowFunction(node)) {
        const oldFunction = currentFunction;

        // Get function name
        if (node.name) {
          currentFunction = node.name.getText(sourceFile);
        } else if (ts.isMethodDeclaration(node) && node.parent && ts.isClassDeclaration(node.parent)) {
          // Method in class
          const className = node.parent.name ? node.parent.name.getText(sourceFile) : 'Anonymous';
          const methodName = node.name ? node.name.getText(sourceFile) : 'anonymous';
          currentFunction = `${className}.${methodName}`;
        }

        ts.forEachChild(node, visit);
        currentFunction = oldFunction;
        return;
      }

      // Extract call expressions
      if (ts.isCallExpression(node) && currentFunction) {
        const { line } = ts.getLineAndCharacterOfPosition(sourceFile, node.getStart());

        let callee = null;
        let isMethod = false;

        // Get callee name
        if (ts.isIdentifier(node.expression)) {
          // Direct call: foo()
          callee = node.expression.getText(sourceFile);
        } else if (ts.isPropertyAccessExpression(node.expression)) {
          // Method call: obj.foo()
          callee = node.expression.name.getText(sourceFile);
          isMethod = true;

          // Try to resolve to symbol for qualified name
          const symbol = typeChecker.getSymbolAtLocation(node.expression.name);
          if (symbol) {
            const declarations = symbol.getDeclarations();
            if (declarations && declarations.length > 0) {
              const decl = declarations[0];
              if (ts.isMethodDeclaration(decl) && decl.parent && ts.isClassDeclaration(decl.parent)) {
                const className = decl.parent.name ? decl.parent.name.getText() : 'Unknown';
                callee = `${className}.${callee}`;
              }
            }
          }
        }

        if (callee) {
          calls.push({
            caller: currentFunction,
            callee: callee,
            line: line,
            isMethod: isMethod
          });
        }
      }

      ts.forEachChild(node, visit);
    }

    visit(sourceFile);

    return { calls };
  } catch (error) {
    return { error: 'CALL_GRAPH_EXTRACTION_FAILED', message: error.message, calls: [] };
  }
}

// === Helper Functions ===

/**
 * Find AST node at a specific position
 */
function findNodeAtPosition(sourceFile, position) {
  function find(node) {
    if (position >= node.getStart() && position < node.getEnd()) {
      return ts.forEachChild(node, find) || node;
    }
  }
  return find(sourceFile);
}

/**
 * Generate symbol fingerprint: file:line:char:symbol
 */
function getSymbolFingerprint(symbol) {
  const declarations = symbol.getDeclarations();
  if (!declarations || declarations.length === 0) {
    return null;
  }

  const declaration = declarations[0];
  const sourceFile = declaration.getSourceFile();
  const { line, character } = ts.getLineAndCharacterOfPosition(
    sourceFile,
    declaration.getStart()
  );

  const relativePath = path.relative(rootDir, sourceFile.fileName);
  return `${relativePath}:${line}:${character}:${symbol.getName()}`;
}

// === JSON-RPC Request Handler ===

function handleRequest(request) {
  const { id, method, params } = request;

  try {
    switch (method) {
      case 'initialize':
        const initResult = initializeProgram(params?.tsconfigPath);
        sendResponse(id, initResult);
        break;

      case 'get_type_at_position':
        const typeResult = getTypeAtPosition(
          params.filePath,
          params.line,
          params.character
        );
        sendResponse(id, typeResult);
        break;

      case 'find_definition':
        const defResult = findDefinition(
          params.filePath,
          params.line,
          params.character
        );
        sendResponse(id, defResult);
        break;

      case 'resolve_import_path':
        const resolveResult = resolveImportPath(
          params.filePath,
          params.importPath
        );
        sendResponse(id, resolveResult);
        break;

      case 'get_diagnostics':
        const diagResult = getDiagnostics(params.filePath);
        sendResponse(id, diagResult);
        break;

      case 'extract_call_graph':
        const callGraphResult = extractCallGraph(params.filePath);
        sendResponse(id, callGraphResult);
        break;

      case 'ping':
        sendResponse(id, { pong: true, timestamp: Date.now() });
        break;

      default:
        sendResponse(id, null, {
          code: -32601,
          message: `Method not found: ${method}`
        });
    }
  } catch (error) {
    sendResponse(id, null, {
      code: -32603,
      message: `Internal error: ${error.message}`
    });
  }
}

// === Main Entry Point ===

function main() {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
  });

  sendNotification('probe_ready', { version: '1.0.0', pid: process.pid });

  rl.on('line', (line) => {
    try {
      const request = JSON.parse(line);
      handleRequest(request);
    } catch (error) {
      // Invalid JSON - send error response if id is present
      sendResponse(null, null, {
        code: -32700,
        message: 'Parse error: Invalid JSON'
      });
    }
  });

  rl.on('close', () => {
    process.exit(0);
  });

  // Handle termination signals
  process.on('SIGINT', () => process.exit(0));
  process.on('SIGTERM', () => process.exit(0));
}

// Start the probe
main();
