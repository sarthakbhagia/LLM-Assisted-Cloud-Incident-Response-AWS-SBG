#!/usr/bin/env node
// check:hardcoded - Guard script to detect hardcoded values in frontend/src
// Usage: npm run check:hardcoded

const fs = require('fs');
const path = require('path');

const SRC_DIR = path.join(__dirname, '..', 'frontend', 'src');

// Patterns that indicate hardcoded/mock/placeholder data
const BANNED_PATTERNS = [
    { pattern: /(mock|dummy|sample|fake|lorem)\b/i, message: "Mock/dummy/placeholder data" },
    { pattern: /Math\.random\(\)/g, message: "Math.random() - simulated data" },
    { pattern: /setTimeout\([^)]*simulated|setTimeout\([^)]*fake|setTimeout\([^)]*mock/gi, message: "setTimeout with simulated data" },
    { pattern: /execute-api\.amazonaws\.com/gi, message: "Literal execute-api URL" },
    { pattern: /(^|\s)(Healthy|Operational)(\s|$)/gi, message: "Hardcoded health status string" },
    { pattern: /Nova Pro|Nova Micro|Claude 3\.5|Llama|Mistral/gi, message: "Hardcoded model name" },
    { pattern: /(threshold|THRESHOLD)\s*[=:]\s*(50000|3000|5000)/gi, message: "Hardcoded threshold value" },
    { pattern: /\.catch\(\(\) => \{\s*\}\)/g, message: "Empty catch block silencing errors" },
    { pattern: /(model_used|BEDROCK_MODEL_ID)\s*[=:]\s*["']?(Nova Pro|Nova Micro|Claude|Llama|Mistral)/gi, message: "Hardcoded model name assignment" },
];

// Files to skip
const SKIP_FILES = [
    'node_modules',
    '.test.',
    '.spec.',
    '.md',
    '.json',
    '.css',
    '.html',
];

let violations = [];

function checkFile(filePath) {
    const relativePath = path.relative(process.cwd(), filePath);
    
    // Skip certain files
    if (SKIP_FILES.some(skip => relativePath.includes(skip))) {
        return;
    }
    
    const content = fs.readFileSync(filePath, 'utf-8');
    const lines = content.split('\n');
    
    lines.forEach((line, lineNum) => {
        BANNED_PATTERNS.forEach(({ pattern, message }) => {
            const matches = line.match(pattern);
            if (matches) {
                violations.push({
                    file: relativePath,
                    line: lineNum + 1,
                    message,
                    matched: matches[0],
                    context: line.trim().substring(0, 120)
                });
            }
        });
    });
}

function walkDir(dir) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
            if (!entry.name.startsWith('.') && entry.name !== 'node_modules') {
                walkDir(fullPath);
            }
        } else if (entry.name.endsWith('.js') || entry.name.endsWith('.jsx') || entry.name.endsWith('.ts') || entry.name.endsWith('.tsx')) {
            checkFile(fullPath);
        }
    }
}

console.log('🔍 Checking for hardcoded/mock/placeholder data in frontend/src...\n');

walkDir(SRC_DIR);

if (violations.length > 0) {
    console.log('❌ FAILED: Found hardcoded/mock/placeholder data:\n');
    violations.forEach(v => {
        console.log(`  ${v.file}:${v.line}`);
        console.log(`    ${v.message}`);
        console.log(`    Matched: "${v.matched}"`);
        console.log(`    Context: ${v.context}`);
        console.log('');
    });
    console.log(`Total violations: ${violations.length}`);
    process.exit(1);
} else {
    console.log('✅ PASSED: No hardcoded/mock/placeholder data found');
    process.exit(0);
}