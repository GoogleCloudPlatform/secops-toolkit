//ucid: 9101
// Source https://github.com/AllThingsComputers/Sentinel-Rules/blob/main/Event%20Logs/Rare%20Scripting%20Software%20Detected.txt

// Title of Detection:   Rare Scripting Software Detected 
// Authorship & Contact: https://allthingscomputers.medium.com  https://twitter.com/allthingshandle  https://allthingscomputersblog.wordpress.com/ 
// Description of the Detection: Because powershell and cmd prompt are so closely watched and have so many alarms put up to catch misuse, hackers are starting to avoid using them. This detects scripting tools that are utilised and found in the Event log that aren't approved software by your environment.
// References (if available): 
// The Logic of the Detection or Query Begins Below This Line
Event
| where (RenderedDescription matches regex@'(?i)(command|shell|execute|script|console|terminal)' or RenderedDescription matches regex @(?i)(Bash|Ksh|Fish|Korn|ZOC|Cmder|ConEmu|Mintty)') and not(RenderedDescription matches regex (Use a regex of your expected tools in your environment to remove false positives))