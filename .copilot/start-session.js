#!/usr/bin/env node
/**
 * Sentinel-D — Daily Session Starter for Dev B
 * Run this at the start of each work session:
 *   node .copilot/start-session.js
 *
 * It prints the exact prompt to paste into Copilot CLI to load the day's context.
 */

const fs = require('fs');
const path = require('path');

// Determine current day based on a start date, or accept --day=N argument
const args = process.argv.slice(2);
const dayArg = args.find(a => a.startsWith('--day='));

let dayNumber;
if (dayArg) {
  dayNumber = parseInt(dayArg.split('=')[1]);
} else {
  // Auto-detect from start date in config
  const configPath = path.join(__dirname, 'config.json');
  if (fs.existsSync(configPath)) {
    const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
    const startDate = new Date(config.projectStartDate);
    const today = new Date();
    const diffMs = today - startDate;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    dayNumber = Math.min(Math.max(diffDays + 1, 1), 14);
  } else {
    dayNumber = 1;
    console.log('⚠️  No config.json found. Defaulting to Day 1.');
    console.log('   Create .copilot/config.json with { "projectStartDate": "YYYY-MM-DD" }');
    console.log('   Or use --day=N to specify the day manually.\n');
  }
}

// Find the right day file
const dayFiles = {
  1: 'days/day-01.md',
  2: 'days/day-02.md',
  3: 'days/day-03.md',
  4: 'days/day-04.md',
  5: 'days/day-05-08.md',   // Day 5 is at top of this file
  6: 'days/day-05-08.md',   // Day 6 is in same file
  7: 'days/day-05-08.md',   // Day 7 is in same file
  8: 'days/day-05-08.md',   // Day 8 is in same file
  9: 'days/day-09-14.md',
  10: 'days/day-09-14.md',
  11: 'days/day-09-14.md',
  12: 'days/day-09-14.md',
  13: 'days/day-09-14.md',
  14: 'days/day-09-14.md',
};

const dayFile = dayFiles[dayNumber];
if (!dayFile) {
  console.error(`No day file for day ${dayNumber}`);
  process.exit(1);
}

const dayFilePath = path.join(__dirname, dayFile);
const dayContent = fs.readFileSync(dayFilePath, 'utf8');

// Extract just today's section (for multi-day files)
let todayContent = dayContent;
if ([5,6,7,8,9,10,11,12,13,14].includes(dayNumber)) {
  const sections = dayContent.split(/---\n---\n\n/);
  const dayIndexInFile = {
    5:0, 6:1, 7:2, 8:3,    // day-05-08.md
    9:0, 10:1, 11:2, 12:3, 13:4, 14:5  // day-09-14.md
  };
  const idx = dayIndexInFile[dayNumber];
  todayContent = sections[idx] || sections[0];
}

// Extract the day title
const titleMatch = todayContent.match(/^# (Day \d+ Goals.*)/m);
const dayTitle = titleMatch ? titleMatch[1] : `Day ${dayNumber}`;

console.log('═'.repeat(60));
console.log(`  SENTINEL-D — ${dayTitle}`);
console.log(`  Dev B Session Starter`);
console.log('═'.repeat(60));
console.log('');
console.log('STEP 1 — Open your terminal in the sentinel-d project root');
console.log('');
console.log('STEP 2 — Start Copilot CLI:');
console.log('');
console.log('  copilot');
console.log('');
console.log('STEP 3 — Copy and paste this prompt into the Copilot session:');
console.log('');
console.log('─'.repeat(60));
console.log('');

const prompt = `I am Dev B (Infrastructure & Integration) on the Sentinel-D project.
My identity, ownership, tech stack, and critical rules are defined in @.github/copilot-instructions.md — please read that first.

Today is Day ${dayNumber}. My goals and tasks for today are in @.copilot/${dayFile}.
${[5,6,7,8].includes(dayNumber) ? `Focus only on the "Day ${dayNumber} Goals" section in that file.` : ''}

Before writing any code, please:
1. Confirm you understand my role as Dev B (not Dev A)
2. Summarise today's goals in 3 bullet points
3. Ask if I want to start with Plan mode (Shift+Tab) for the first major task, or dive straight in

Let's start.`;

console.log(prompt);
console.log('');
console.log('─'.repeat(60));
console.log('');
console.log('STEP 4 — After pasting the prompt:');
console.log('  - For complex implementation tasks: press Shift+Tab for Plan mode first');
console.log('  - Use @filename to pull specific schema files into context');
console.log('  - Use /diff at end of day to review all changes');
console.log('  - Use /review before any commit');
console.log('');
console.log('USEFUL REFERENCES FOR TODAY:');
if (dayNumber <= 2) console.log('  @shared/schemas/ — all 8 JSON schemas (frozen after Day 1)');
if (dayNumber >= 3) console.log('  @.github/copilot-instructions.md — your identity and ownership');
console.log('');

// Print today's success criteria
const criteriaMatch = todayContent.match(/## SUCCESS CRITERIA[\s\S]*?(?=\n---|\n# Day|\Z)/);
if (criteriaMatch) {
  console.log('TODAY\'S SUCCESS CRITERIA:');
  console.log(criteriaMatch[0]);
}
